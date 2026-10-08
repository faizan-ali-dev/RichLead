from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Q
from django.db.models.functions import TruncDate, Trim
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from ai_engine.models import BusinessProfile
from async_jobs.models import BackgroundJob
from integrations.models import APIIntegration, EmailAccount
from .models import AnalyticsEvent, SocialLink
from .permissions import IsSuperuser
from .serializers import AdminUserUpdateSerializer, AnalyticsEventSerializer, PublicSocialLinkSerializer

User = get_user_model()
ALLOWED_PERIODS = {7, 30, 90, 365}
FORBIDDEN_ADMIN_FIELDS = {'email', 'username', 'password', 'is_staff', 'is_superuser', 'groups', 'user_permissions'}
LLM_PROVIDER_LABELS = {'openai': 'OpenAI', 'anthropic': 'Anthropic', 'groq': 'Groq'}
PROVIDER_LABELS = {**LLM_PROVIDER_LABELS, 'apollo': 'Apollo', 'hunter': 'Hunter'}
LLM_JOB_TYPES = ('generate_draft', 'draft_queue', 'classify_replies')
ADOPTION_JOB_TYPES = (*LLM_JOB_TYPES, 'apollo_search', 'hunter_search', 'inbox_sync')


class SiteAnalyticsThrottle(AnonRateThrottle):
    scope = 'site_analytics'


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([SiteAnalyticsThrottle])
def track_event(request):
    serializer = AnalyticsEventSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    event = serializer.validated_data
    AnalyticsEvent.objects.create(**event)
    return Response(status=status.HTTP_202_ACCEPTED)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_social_links(request):
    links = SocialLink.objects.filter(is_active=True).order_by('display_order', 'id')
    return Response(PublicSocialLinkSerializer(links, many=True).data)


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_access(request):
    return Response({'is_admin': True, 'admin_id': request.user.pk})


def _get_period(request):
    try:
        days = int(request.query_params.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    return days if days in ALLOWED_PERIODS else 30


def _window(days):
    now = timezone.now()
    today = timezone.localdate(now)
    start_day = today - timedelta(days=days - 1)
    tz = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end_at = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)
    return now, today, start_day, start_at, end_at


def _job_usage(total=0, succeeded=0, failed=0, last_run=None):
    return {
        'runs_30d': total,
        'succeeded_30d': succeeded,
        'failed_30d': failed,
        'last_run_at': last_run,
    }


def _user_adoption(user_ids):
    """Return setup status and aggregate product activity without tenant content."""
    user_ids = list(user_ids)
    if not user_ids:
        return {}

    adoption = {
        user_id: {
            'business_profile': {'status': 'not_started', 'icp_configured': False},
            'llm': {
                'status': 'not_configured', 'providers': [], 'configured_providers': [],
                'primary_provider': '', 'last_validated_at': None,
            },
            'apollo': {'status': 'not_configured', **_job_usage()},
            'hunter': {'status': 'not_configured', **_job_usage()},
            'ai_activity': _job_usage(),
            'mailbox': {'connected_count': 0, 'sync': _job_usage()},
        }
        for user_id in user_ids
    }

    profile_fields = (
        'user_id', 'company_name', 'website', 'industry', 'what_you_do', 'problem_you_solve',
        'ideal_customer', 'differentiator', 'proof_points', 'case_study', 'never_claim',
        'sender_name', 'sender_title', 'icp_titles', 'icp_industries', 'icp_locations',
        'icp_employee_min', 'icp_employee_max', 'icp_requires_funding',
    )
    for profile in BusinessProfile.objects.filter(user_id__in=user_ids).values(*profile_fields):
        text_fields = (
            'company_name', 'website', 'industry', 'what_you_do', 'problem_you_solve',
            'ideal_customer', 'differentiator', 'proof_points', 'case_study', 'never_claim',
            'sender_name', 'sender_title',
        )
        has_details = any((profile[field] or '').strip() for field in text_fields)
        has_icp = bool(
            profile['icp_titles'] or profile['icp_industries'] or profile['icp_locations']
            or profile['icp_employee_min'] is not None or profile['icp_employee_max'] is not None
            or profile['icp_requires_funding']
        )
        complete = bool((profile['what_you_do'] or '').strip() and (profile['problem_you_solve'] or '').strip())
        adoption[profile['user_id']]['business_profile'] = {
            'status': 'complete' if complete else 'started' if has_details or has_icp else 'not_started',
            'icp_configured': has_icp,
        }

    for integration in APIIntegration.objects.filter(
        user_id__in=user_ids,
        provider__in=PROVIDER_LABELS,
    ).exclude(encrypted_api_key='').values(
        'user_id', 'provider', 'is_active', 'is_primary', 'last_validated_at',
    ):
        item = adoption[integration['user_id']]
        provider = integration['provider']
        label = PROVIDER_LABELS[provider]
        if provider in LLM_PROVIDER_LABELS:
            llm = item['llm']
            llm['configured_providers'].append(label)
            if integration['is_active']:
                llm['providers'].append(label)
            if integration['is_active'] and integration['is_primary']:
                llm['primary_provider'] = label
            if integration['last_validated_at'] and (
                llm['last_validated_at'] is None
                or integration['last_validated_at'] > llm['last_validated_at']
            ):
                llm['last_validated_at'] = integration['last_validated_at']
        else:
            item[provider]['status'] = 'connected' if integration['is_active'] else 'paused'

    for item in adoption.values():
        llm = item['llm']
        if llm['providers']:
            llm['status'] = 'connected'
        elif llm['configured_providers']:
            llm['status'] = 'paused'

    recent_jobs = BackgroundJob.objects.filter(
        user_id__in=user_ids,
        job_type__in=ADOPTION_JOB_TYPES,
        created_at__gte=timezone.now() - timedelta(days=30),
    ).values('user_id', 'job_type').annotate(
        total=Count('pk'),
        succeeded=Count('pk', filter=Q(status='succeeded')),
        failed=Count('pk', filter=Q(status='failed')),
        last_run=Max('created_at'),
    )
    for row in recent_jobs:
        item = adoption[row['user_id']]
        usage = _job_usage(row['total'], row['succeeded'], row['failed'], row['last_run'])
        if row['job_type'] == 'apollo_search':
            item['apollo'].update(usage)
        elif row['job_type'] == 'hunter_search':
            item['hunter'].update(usage)
        elif row['job_type'] == 'inbox_sync':
            item['mailbox']['sync'] = usage
        elif row['job_type'] in LLM_JOB_TYPES:
            ai = item['ai_activity']
            ai['runs_30d'] += usage['runs_30d']
            ai['succeeded_30d'] += usage['succeeded_30d']
            ai['failed_30d'] += usage['failed_30d']
            if usage['last_run_at'] and (ai['last_run_at'] is None or usage['last_run_at'] > ai['last_run_at']):
                ai['last_run_at'] = usage['last_run_at']

    for row in EmailAccount.objects.filter(user_id__in=user_ids, is_connected=True).values('user_id').annotate(
        connected_count=Count('pk'),
    ):
        adoption[row['user_id']]['mailbox']['connected_count'] = row['connected_count']

    return adoption


def _product_adoption_summary(customer_users):
    """Platform-wide adoption totals; never returns tenant settings or content."""
    profiles = BusinessProfile.objects.filter(user__in=customer_users).annotate(
        trimmed_offer=Trim('what_you_do'),
        trimmed_problem=Trim('problem_you_solve'),
    )
    complete_profiles = profiles.exclude(trimmed_offer='').exclude(trimmed_problem='').count()
    profile_has_data = (
        Q(company_name__gt='') | Q(website__gt='') | Q(industry__gt='')
        | Q(what_you_do__gt='') | Q(problem_you_solve__gt='') | Q(ideal_customer__gt='')
        | Q(differentiator__gt='') | Q(proof_points__gt='') | Q(case_study__gt='')
        | Q(never_claim__gt='') | Q(sender_name__gt='') | Q(sender_title__gt='')
        | ~Q(icp_titles=[]) | ~Q(icp_industries=[]) | ~Q(icp_locations=[])
        | Q(icp_employee_min__isnull=False) | Q(icp_employee_max__isnull=False)
        | Q(icp_requires_funding=True)
    )
    started_profiles = profiles.filter(profile_has_data).exclude(
        trimmed_offer__gt='', trimmed_problem__gt='',
    ).count()

    integrations = APIIntegration.objects.filter(user__in=customer_users, is_active=True).exclude(encrypted_api_key='')
    connected_users = {
        row['provider']: row['users']
        for row in integrations.values('provider').annotate(users=Count('user_id', distinct=True))
    }
    llm_connected_users = integrations.filter(provider__in=LLM_PROVIDER_LABELS).values('user_id').distinct().count()
    recent_jobs = BackgroundJob.objects.filter(
        user__in=customer_users,
        job_type__in=ADOPTION_JOB_TYPES,
        created_at__gte=timezone.now() - timedelta(days=30),
    )
    job_counts = {
        row['job_type']: row['total']
        for row in recent_jobs.values('job_type').annotate(total=Count('pk'))
    }
    return {
        'business_profiles_complete': complete_profiles,
        'business_profiles_started': started_profiles,
        'llm_connected_users': llm_connected_users,
        'apollo_connected_users': connected_users.get('apollo', 0),
        'hunter_connected_users': connected_users.get('hunter', 0),
        'mailbox_connected_users': EmailAccount.objects.filter(
            user__in=customer_users, is_connected=True,
        ).values('user_id').distinct().count(),
        'ai_jobs_30d': sum(job_counts.get(job_type, 0) for job_type in LLM_JOB_TYPES),
        'apollo_searches_30d': job_counts.get('apollo_search', 0),
        'hunter_searches_30d': job_counts.get('hunter_search', 0),
    }


def _timeseries(start_day, today, start_at, end_at):
    customer_users = User.objects.filter(is_staff=False, is_superuser=False)
    event_rows = {
        row['day']: row
        for row in AnalyticsEvent.objects.filter(created_at__gte=start_at, created_at__lt=end_at)
        .annotate(day=TruncDate('created_at', tzinfo=timezone.get_current_timezone()))
        .values('day')
        .annotate(
            page_views=Count('id', filter=Q(event_type='page_view')),
            unique_visitors=Count('session_id', filter=Q(event_type='page_view'), distinct=True),
            clicks=Count('id', filter=Q(event_type='cta_click')),
        )
    }
    signup_rows = {
        row['day']: row['signups']
        for row in customer_users.filter(date_joined__gte=start_at, date_joined__lt=end_at)
        .annotate(day=TruncDate('date_joined', tzinfo=timezone.get_current_timezone()))
        .values('day')
        .annotate(signups=Count('pk'))
    }

    series = []
    day = start_day
    while day <= today:
        event_row = event_rows.get(day, {})
        series.append({
            'date': day.isoformat(),
            'label': day.strftime('%b %d').replace(' 0', ' '),
            'page_views': event_row.get('page_views', 0),
            'unique_visitors': event_row.get('unique_visitors', 0),
            'clicks': event_row.get('clicks', 0),
            'signups': signup_rows.get(day, 0),
        })
        day += timedelta(days=1)
    return series


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_overview(request):
    days = _get_period(request)
    now, today, start_day, start_at, end_at = _window(days)
    window_events = AnalyticsEvent.objects.filter(created_at__gte=start_at, created_at__lt=end_at)
    traffic = window_events.aggregate(
        page_views=Count('id', filter=Q(event_type='page_view')),
        unique_visitors=Count('session_id', filter=Q(event_type='page_view'), distinct=True),
        clicks=Count('id', filter=Q(event_type='cta_click')),
    )
    customer_users = User.objects.filter(is_staff=False, is_superuser=False)
    signups = customer_users.filter(date_joined__gte=start_at, date_joined__lt=end_at).count()

    top_pages = list(
        window_events.filter(event_type='page_view')
        .values('path')
        .annotate(
            page_views=Count('id'),
            unique_visitors=Count('session_id', distinct=True),
        )
        .order_by('-page_views', 'path')[:8]
    )
    top_clicks = list(
        window_events.filter(event_type='cta_click')
        .values('label')
        .annotate(clicks=Count('id'))
        .order_by('-clicks', 'label')[:8]
    )
    recent_signups = [
        {
            'id': user.pk,
            'full_name': user.get_full_name().strip(),
            'email': user.email,
            'date_joined': user.date_joined,
            'email_verified': user.email_verified,
            'is_active': user.is_active,
        }
        for user in customer_users.order_by('-date_joined')[:8]
    ]
    product_adoption = _product_adoption_summary(customer_users)

    visitor_count = traffic['unique_visitors'] or 0
    return Response({
        'period_days': days,
        'generated_at': now,
        'summary': {
            'total_users': customer_users.count(),
            'active_users': customer_users.filter(is_active=True).count(),
            'verified_users': customer_users.filter(email_verified=True).count(),
            'new_signups': signups,
            'page_views': traffic['page_views'] or 0,
            'unique_visitors': visitor_count,
            'cta_clicks': traffic['clicks'] or 0,
            'signup_rate': round(signups * 100 / visitor_count, 1) if visitor_count else 0,
        },
        'series': _timeseries(start_day, today, start_at, end_at),
        'top_pages': top_pages,
        'top_clicks': top_clicks,
        'recent_signups': recent_signups,
        'product_adoption': product_adoption,
    })


@api_view(['GET'])
@permission_classes([IsSuperuser])
def admin_users(request):
    try:
        page_size = min(max(int(request.query_params.get('page_size', 25)), 1), 100)
        page = max(int(request.query_params.get('page', 1)), 1)
    except (TypeError, ValueError):
        page_size = 25
        page = 1

    query = request.query_params.get('q', '').strip()[:100]
    user_filter = request.query_params.get('status', 'all')
    users = User.objects.filter(is_staff=False, is_superuser=False)
    if query:
        users = users.filter(
            Q(email__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(nickname__icontains=query)
        )
    if user_filter == 'active':
        users = users.filter(is_active=True)
    elif user_filter == 'suspended':
        users = users.filter(is_active=False)
    elif user_filter == 'unverified':
        users = users.filter(email_verified=False)

    total = users.count()
    page_count = max((total + page_size - 1) // page_size, 1)
    page = min(page, page_count)
    rows = users.order_by('-date_joined')[((page - 1) * page_size):(page * page_size)]
    rows = list(rows)
    adoption_by_user = _user_adoption(user.pk for user in rows)
    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'page_count': page_count,
        'results': [
            {
                'id': user.pk,
                'full_name': user.get_full_name().strip(),
                'nickname': user.nickname,
                'email': user.email,
                'email_verified': user.email_verified,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
                'adoption': adoption_by_user[user.pk],
            }
            for user in rows
        ],
    })


@api_view(['PATCH'])
@permission_classes([IsSuperuser])
def admin_user_detail(request, user_id):
    forbidden = FORBIDDEN_ADMIN_FIELDS.intersection(request.data.keys())
    if forbidden:
        return Response(
            {'detail': 'Email and permission changes must use their protected account flows.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = AdminUserUpdateSerializer(data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if not serializer.validated_data:
        return Response({'detail': 'Provide at least one supported user setting.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(pk=user_id, is_staff=False, is_superuser=False)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    updates = serializer.validated_data

    changed_fields = []
    if 'full_name' in updates:
        first_name, _, last_name = updates['full_name'].partition(' ')
        if (user.first_name, user.last_name) != (first_name, last_name):
            user.first_name, user.last_name = first_name, last_name
            changed_fields.extend(['first_name', 'last_name'])
    for field in ('nickname', 'is_active', 'email_verified'):
        if field in updates and getattr(user, field) != updates[field]:
            setattr(user, field, updates[field])
            changed_fields.append(field)

    if changed_fields:
        user.save(update_fields=changed_fields)

    return Response({
        'id': user.pk,
        'full_name': user.get_full_name().strip(),
        'nickname': user.nickname,
        'email': user.email,
        'email_verified': user.email_verified,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': user.date_joined,
        'last_login': user.last_login,
    })
