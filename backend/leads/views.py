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
        return (
            Lead.objects.filter(user=self.request.user)
            .select_related('research')
            .prefetch_related('score_breakdowns', 'intent_signals')
            .order_by('-id')
        )

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
