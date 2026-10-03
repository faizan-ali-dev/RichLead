from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .models import AnalyticsEvent, SocialLink
from .permissions import IsSuperuser
from .serializers import AdminUserUpdateSerializer, AnalyticsEventSerializer, PublicSocialLinkSerializer

User = get_user_model()
ALLOWED_PERIODS = {7, 30, 90, 365}
FORBIDDEN_ADMIN_FIELDS = {'email', 'username', 'password', 'is_staff', 'is_superuser', 'groups', 'user_permissions'}


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
