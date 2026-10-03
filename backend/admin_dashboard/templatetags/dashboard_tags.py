from datetime import date, datetime, time, timedelta

from django import template
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from admin_dashboard.models import AnalyticsEvent, LoginActivity

register = template.Library()
User = get_user_model()
ALLOWED_PERIODS = {7, 30, 90, 365}


def _period(request):
    try:
        requested = int(request.GET.get('days', 30))
    except (TypeError, ValueError):
        return 30
    return requested if requested in ALLOWED_PERIODS else 30


def _bucket_dates(start_day, today, monthly):
    if not monthly:
        current = start_day
        while current <= today:
            yield current
            current += timedelta(days=1)
        return

    current = date(start_day.year, start_day.month, 1)
    end = date(today.year, today.month, 1)
    while current <= end:
        yield current
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)


def _bucket_counts(queryset, field, truncation, tz):
    rows = queryset.annotate(bucket=truncation(field, tzinfo=tz)).values('bucket').annotate(total=Count('pk'))
    counts = {}
    for row in rows:
        bucket = row['bucket']
        if isinstance(bucket, datetime):
            bucket = bucket.date()
        counts[bucket.replace(day=1) if truncation is TruncMonth else bucket] = row['total']
    return counts


@register.simple_tag(takes_context=True)
def richlead_admin_summary(context):
    """Build the limited, platform-level information shown on the admin home."""
    request = context['request']
    days = _period(request)
    now = timezone.now()
    today = timezone.localdate(now)
    start_day = today - timedelta(days=days - 1)
    tz = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(start_day, time.min), tz)
    end_at = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min), tz)
    monthly = days == 365
    truncation = TruncMonth if monthly else TruncDate

    signups = _bucket_counts(
        User.objects.filter(
            is_staff=False, is_superuser=False, date_joined__gte=start_at, date_joined__lt=end_at,
        ), 'date_joined', truncation, tz,
    )
    logins = _bucket_counts(
        LoginActivity.objects.filter(
            user__is_staff=False, user__is_superuser=False, logged_in_at__gte=start_at, logged_in_at__lt=end_at,
        ), 'logged_in_at', truncation, tz,
    )
    event_window = AnalyticsEvent.objects.filter(created_at__gte=start_at, created_at__lt=end_at)
    page_views = _bucket_counts(
        event_window.filter(event_type='page_view'), 'created_at', truncation, tz,
    )
    clicks = _bucket_counts(
        event_window.filter(event_type='cta_click'), 'created_at', truncation, tz,
    )

    points = []
    for bucket in _bucket_dates(start_day, today, monthly):
        signup_count = signups.get(bucket, 0)
        login_count = logins.get(bucket, 0)
        page_view_count = page_views.get(bucket, 0)
        click_count = clicks.get(bucket, 0)
        label = bucket.strftime('%b') if monthly else bucket.strftime('%b %d').replace(' 0', ' ')
        points.append({
            'label': label,
            'signups': signup_count,
            'logins': login_count,
            'page_views': page_view_count,
            'clicks': click_count,
        })

    maximum = max((max(point['signups'], point['logins']) for point in points), default=0)
    for point in points:
        point['signup_height'] = round(point['signups'] * 100 / maximum) if maximum else 0
        point['login_height'] = round(point['logins'] * 100 / maximum) if maximum else 0
    traffic_maximum = max((max(point['page_views'], point['clicks']) for point in points), default=0)
    for point in points:
        point['page_view_height'] = round(point['page_views'] * 100 / traffic_maximum) if traffic_maximum else 0
        point['click_height'] = round(point['clicks'] * 100 / traffic_maximum) if traffic_maximum else 0
    event_summary = event_window.aggregate(
        page_views=Count('id', filter=Q(event_type='page_view')),
        visitors=Count(
            'session_id', filter=Q(event_type='page_view'), distinct=True,
        ),
        clicks=Count('id', filter=Q(event_type='cta_click')),
    )

    return {
        'days': days,
        'total_users': User.objects.filter(is_staff=False, is_superuser=False).count(),
        'active_users': User.objects.filter(is_staff=False, is_superuser=False, is_active=True).count(),
        'inactive_users': User.objects.filter(is_staff=False, is_superuser=False, is_active=False).count(),
        'new_signups': User.objects.filter(is_staff=False, is_superuser=False, date_joined__gte=start_at, date_joined__lt=end_at).count(),
        'login_count': LoginActivity.objects.filter(
            user__is_staff=False, user__is_superuser=False, logged_in_at__gte=start_at, logged_in_at__lt=end_at,
        ).count(),
        'page_views': event_summary['page_views'] or 0,
        'visitors': event_summary['visitors'] or 0,
        'cta_clicks': event_summary['clicks'] or 0,
        'points': points,
        'login_history_available': LoginActivity.objects.filter(
            user__is_staff=False, user__is_superuser=False,
        ).exists(),
        'growth_data_available': any(point['signups'] or point['logins'] for point in points),
        'traffic_data_available': any(point['page_views'] or point['clicks'] for point in points),
        'recent_logins': LoginActivity.objects.filter(
            user__is_staff=False, user__is_superuser=False,
        ).select_related('user').order_by('-logged_in_at')[:10],
        'recent_signups': User.objects.filter(is_staff=False, is_superuser=False).order_by('-date_joined')[:8],
        'range_label': 'past 12 months' if monthly else f'past {days} days',
    }
