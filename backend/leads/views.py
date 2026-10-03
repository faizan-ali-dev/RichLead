from datetime import datetime, time, timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from inbox.models import EmailMessage
from integrations.models import SuppressionEntry
from richlead_backend.caching import cache_call
from .models import AIResearch, Lead
from .serializers import LeadSerializer

class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # The serializer walks score_breakdowns, intent_signals and research for every
        # row; without prefetching that is 3 extra queries per lead.
        queryset = (
            Lead.objects.filter(user=self.request.user)
            .select_related('research')
            .prefetch_related('score_breakdowns', 'intent_signals')
        )
        params = self.request.query_params

        status_filter = params.get('status')
        if status_filter in dict(Lead.STATUS_CHOICES):
            queryset = queryset.filter(status=status_filter)

        source_filter = params.get('source')
        if source_filter and source_filter.lower() != 'all':
            if source_filter.lower() == 'manual':
                queryset = queryset.filter(Q(source__iexact='manual') | Q(source=''))
            else:
                queryset = queryset.filter(source__iexact=source_filter[:50])

        email_status = params.get('email_status')
        if email_status in dict(Lead.EMAIL_STATUS_CHOICES):
            queryset = queryset.filter(email_status=email_status)

        for parameter, field in (('industry', 'industry'), ('location', 'location')):
            value = params.get(parameter, '').strip()
            if value:
                queryset = queryset.filter(**{f'{field}__icontains': value[:150]})

        search = params.get('search', '').strip()
        if search:
            search_filter = Q()
            for field in (
                'name', 'company', 'email', 'phone', 'title', 'niche', 'industry',
                'location', 'website', 'linkedin_url', 'funding_amount', 'funding_round',
            ):
                search_filter |= Q(**{f'{field}__icontains': search[:255]})
            queryset = queryset.filter(search_filter)

        min_icp = params.get('min_icp')
        if min_icp is not None:
            try:
                min_icp = int(min_icp)
            except (TypeError, ValueError):
                min_icp = None
            if min_icp is not None and 0 <= min_icp <= 100:
                queryset = queryset.filter(icp_score__gte=min_icp)

        employee_range = params.get('employee_range')
        employee_ranges = {
            '1-10': (1, 10),
            '11-50': (11, 50),
            '51-200': (51, 200),
        }
        if employee_range in employee_ranges:
            lower, upper = employee_ranges[employee_range]
            queryset = queryset.filter(employee_count__gte=lower, employee_count__lte=upper)
        elif employee_range == '201+':
            queryset = queryset.filter(employee_count__gte=201)

        contact_info = params.get('contact_info')
        if contact_info == 'has_phone':
            queryset = queryset.exclude(phone='')
        elif contact_info == 'no_phone':
            queryset = queryset.filter(phone='')
        elif contact_info == 'has_website':
            queryset = queryset.exclude(website='')
        elif contact_info == 'no_website':
            queryset = queryset.filter(website='')

        ordering = params.get('ordering')
        if ordering in {'-icp_score', 'icp_score', 'name'}:
            queryset = queryset.order_by(ordering, 'id')
        else:
            queryset = queryset.order_by('-id')
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    day = timezone.localdate()
    data = cache_call(
        'dashboard-stats',
        parts={'user_id': request.user.pk, 'day': day.isoformat()},
        timeout=settings.CACHE_DASHBOARD_STATS_TTL,
        producer=lambda: _build_dashboard_stats(request.user, today=day),
    )
    return Response(data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def lead_quality_view(request):
    """Summarize verified status, contact readiness, and fixable profile gaps."""
    user = request.user
    leads = Lead.objects.filter(user=user)
    suppressions = list(SuppressionEntry.objects.filter(user=user).values('email', 'domain'))
    suppressed_emails = [entry['email'] for entry in suppressions if entry['email']]
    suppressed_domains = [entry['domain'] for entry in suppressions if entry['domain']]
    suppressed_filter = Q()
    has_suppressions = bool(suppressed_emails or suppressed_domains)
    if suppressed_emails:
        suppressed_filter |= Q(email__in=suppressed_emails)
    for domain in suppressed_domains:
        suppressed_filter |= Q(email__iendswith=f'@{domain}')

    if has_suppressions:
        suppressed_count = leads.filter(suppressed_filter).count()
        ready = leads.filter(status='pending', email_status='verified').exclude(suppressed_filter)
    else:
        suppressed_count = 0
        ready = leads.filter(status='pending', email_status='verified')

    totals = leads.aggregate(
        total=Count('id'),
        verified=Count('id', filter=Q(email_status='verified')),
        unknown=Count('id', filter=Q(email_status='unknown')),
        not_verified=Count('id', filter=Q(email_status='not_verified')),
        high_fit=Count('id', filter=Q(icp_score__gte=80)),
        complete_profiles=Count(
            'id',
            filter=(~Q(company='') & ~Q(company='Unknown company') & ~Q(title='') & ~Q(website='')),
        ),
    )

    attention_filter = (
        Q(email_status__in=('unknown', 'not_verified'))
        | Q(company='') | Q(company='Unknown company') | Q(title='') | Q(website='')
        | Q(icp_score__lt=80)
    )
    if has_suppressions:
        attention_filter |= suppressed_filter
    attention_rows = list(
        leads.filter(attention_filter)
        .order_by('-created_at', '-id')
        .values('id', 'name', 'company', 'email', 'email_status', 'website', 'title', 'icp_score')[:20]
    )
    ready_count = ready.count()
    needs_attention = leads.filter(attention_filter).count()
    entries_by_email = {entry['email'] for entry in suppressions if entry['email']}
    for row in attention_rows:
        row['flags'] = []
        if row['email_status'] != 'verified':
            row['flags'].append('Verify work email')
        if not row['company'] or row['company'] == 'Unknown company':
            row['flags'].append('Add company')
        if not row['title']:
            row['flags'].append('Add job title')
        if not row['website']:
            row['flags'].append('Add website')
        if row['icp_score'] < 80:
            row['flags'].append('Review fit')
        domain = row['email'].rsplit('@', 1)[-1].lower() if '@' in row['email'] else ''
        if row['email'].lower() in entries_by_email or domain in suppressed_domains:
            row['flags'].append('Suppressed, do not contact')

    return Response({
        'summary': {
            **totals,
            'suppressed': suppressed_count,
            'ready_to_contact': ready_count,
            'needs_attention': needs_attention,
        },
        'attention_leads': attention_rows,
        'verification_note': 'Apollo and Hunter contacts are marked verified only after their provider confirms a valid work email. Manually added leads are not checked automatically.',
    })


def _build_dashboard_stats(user, *, today=None):
    """Tenant dashboard counters, computed in a single aggregate pass.

    Sends and replies come from event timestamps rather than `status`: a lead that
    replies is still a lead that was sent to, and must stay in the denominator.
    """
    stats = Lead.objects.filter(user=user).aggregate(
        leads_discovered=Count('id'),
        qualified=Count('id', filter=Q(icp_score__gt=80)),
        ai_researched=Count('id', filter=Q(research__isnull=False)),
        messages_generated=Count(
            'id',
            filter=Q(research__isnull=False) & ~Q(research__generated_message=''),
        ),
        pending_review=Count('id', filter=Q(status='pending')),
        messages_sent=Count('id', filter=Q(first_sent_at__isnull=False)),
        replies=Count('id', filter=Q(replied_at__isnull=False)),
    )

    sent = stats['messages_sent']
    reply_rate = round((stats['replies'] / sent * 100) if sent else 0.0, 1)

    # Build the chart from persisted mail and bounce records. A lead's first_sent_at
    # only captures one touch, so EmailMessage is the source for actual send volume.
    current_tz = timezone.get_current_timezone()
    today = today or timezone.localdate()
    first_day = today - timedelta(days=6)
    range_start = timezone.make_aware(datetime.combine(first_day, time.min), current_tz)
    range_end = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), current_tz)

    def daily_counts(queryset, field):
        rows = (
            queryset.filter(**{f'{field}__gte': range_start, f'{field}__lt': range_end})
            .annotate(day=TruncDate(field, tzinfo=current_tz))
            .values('day')
            .annotate(total=Count('id'))
        )
        return {row['day']: row['total'] for row in rows}

    sent_by_day = daily_counts(
        EmailMessage.objects.filter(user=user, direction='outbound'), 'received_at'
    )
    replies_by_day = daily_counts(
        EmailMessage.objects.filter(user=user, direction='inbound', lead__isnull=False),
        'received_at',
    )
    bounces_by_day = daily_counts(
        SuppressionEntry.objects.filter(user=user, reason='bounced'), 'created_at'
    )

    analytics = [
        {
            'name': (first_day + timedelta(days=offset)).strftime('%a'),
            'date': (first_day + timedelta(days=offset)).isoformat(),
            'sent': sent_by_day.get(first_day + timedelta(days=offset), 0),
            'replies': replies_by_day.get(first_day + timedelta(days=offset), 0),
            'bounces': bounces_by_day.get(first_day + timedelta(days=offset), 0),
        }
        for offset in range(7)
    ]

    activity = []
    user_leads = Lead.objects.filter(user=user)
    for lead in user_leads.order_by('-created_at')[:10]:
        activity.append({
            'id': f'lead-{lead.id}',
            'type': 'lead',
            'title': f'Lead added: {lead.name or lead.company}',
            'occurred_at': lead.created_at,
        })

    for message in (
        EmailMessage.objects.filter(user=user)
        .select_related('lead')
        .order_by('-received_at')[:20]
    ):
        if message.direction == 'outbound':
            event_type = 'sent'
            title = f'Email sent to {message.lead.name}' if message.lead else 'Outbound email sent'
        elif message.lead_id:
            event_type = 'reply'
            title = f'Reply received from {message.lead.name}'
        else:
            event_type = 'inbound'
            title = 'Inbox email received'
        activity.append({
            'id': f'email-{message.id}',
            'type': event_type,
            'title': title,
            'occurred_at': message.received_at,
        })

    for research in (
        AIResearch.objects.filter(lead__user=user)
        .select_related('lead')
        .order_by('-created_at')[:10]
    ):
        activity.append({
            'id': f'research-{research.id}',
            'type': 'research',
            'title': f'Personalized message generated for {research.lead.name}',
            'occurred_at': research.created_at,
        })

    for bounce in (
        SuppressionEntry.objects.filter(user=user, reason='bounced')
        .order_by('-created_at')[:10]
    ):
        activity.append({
            'id': f'bounce-{bounce.id}',
            'type': 'bounce',
            'title': 'Email address recorded as bounced',
            'occurred_at': bounce.created_at,
        })

    activity.sort(key=lambda item: item['occurred_at'], reverse=True)
    recent_activity = [
        {
            **item,
            'occurred_at': item['occurred_at'].isoformat(),
        }
        for item in activity[:10]
    ]

    return {
        **stats,
        'reply_rate': f"{reply_rate}%",
        'analytics': analytics,
        'recent_activity': recent_activity,
    }
