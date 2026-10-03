"""Tenant-scoped outreach workflow and sender-health APIs."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone
from rest_framework import permissions, status, views
from rest_framework.response import Response

from ai_engine.business import FollowUpSettings
from inbox.models import EmailMessage
from .models import APIIntegration, EmailAccount, FollowUpSequence, SuppressionEntry, is_suppressed


def _sequence_payload(sequence, total_follow_ups):
    return {
        'id': sequence.id,
        'status': sequence.status,
        'lead': {
            'id': sequence.lead_id,
            'name': sequence.lead.name,
            'company': sequence.lead.company,
            'email': sequence.lead.email,
        },
        'sent_follow_ups': sequence.sent_follow_ups,
        'total_follow_ups': total_follow_ups,
        'next_step': min(sequence.sent_follow_ups + 1, total_follow_ups),
        'next_send_at': sequence.next_send_at,
        'last_sent_at': sequence.last_sent_at,
        'needs_review': sequence.status == 'failed',
    }


class FollowUpSequenceView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        settings_obj, _ = FollowUpSettings.objects.get_or_create(user=user)
        sequences = FollowUpSequence.objects.filter(user=user).select_related('lead')
        counts = sequences.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
            paused=Count('id', filter=Q(status='paused')),
            completed=Count('id', filter=Q(status='completed')),
            stopped=Count('id', filter=Q(status='stopped')),
            needs_review=Count('id', filter=Q(status='failed')),
        )
        rows = list(sequences.order_by(
            Case(
                When(status='active', then=Value(0)),
                When(status='paused', then=Value(1)),
                When(status='failed', then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            ),
            'next_send_at',
            'id',
        )[:100])
        connected_senders = EmailAccount.objects.filter(user=user, is_connected=True).count()
        ai_ready = APIIntegration.objects.filter(user=user, is_active=True, is_primary=True).exists()
        return Response({
            'settings': {
                'enabled': settings_obj.enabled,
                'total_follow_ups': settings_obj.total_follow_ups,
                'days_between': settings_obj.days_between,
                'stop_on_reply': settings_obj.stop_on_reply,
            },
            'counts': counts,
            'total': counts['total'],
            'has_more': counts['total'] > len(rows),
            'readiness': {
                'sender_connected': connected_senders > 0,
                'connected_sender_count': connected_senders,
                'ai_connected': ai_ready,
                'follow_ups_enabled': settings_obj.enabled and settings_obj.total_follow_ups > 0,
            },
            'items': [_sequence_payload(row, settings_obj.total_follow_ups) for row in rows],
        })

    def post(self, request, sequence_id):
        action = request.data.get('action')
        if action not in {'pause', 'resume', 'stop'}:
            return Response({'detail': 'Choose pause, resume, or stop.'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            sequence = FollowUpSequence.objects.select_for_update().select_related('lead').filter(
                user=request.user, pk=sequence_id,
            ).first()
            if sequence is None:
                return Response({'detail': 'Sequence not found.'}, status=status.HTTP_404_NOT_FOUND)
            if sequence.claim_token:
                return Response(
                    {'detail': 'This sequence is being processed. Try again in a moment.'},
                    status=status.HTTP_409_CONFLICT,
                )

            if action == 'pause':
                if sequence.status != 'active':
                    return Response({'detail': 'Only an active sequence can be paused.'}, status=status.HTTP_409_CONFLICT)
                sequence.status = 'paused'
            elif action == 'stop':
                if sequence.status not in {'active', 'paused'}:
                    return Response({'detail': 'This sequence is already finished.'}, status=status.HTTP_409_CONFLICT)
                sequence.status = 'stopped'
            else:
                if sequence.status != 'paused':
                    return Response({'detail': 'Only a paused sequence can be resumed.'}, status=status.HTTP_409_CONFLICT)
                settings_obj, _ = FollowUpSettings.objects.get_or_create(user=request.user)
                if not settings_obj.enabled or sequence.sent_follow_ups >= settings_obj.total_follow_ups:
                    return Response(
                        {'detail': 'Enable follow-ups and set at least one remaining step in Outreach settings first.'},
                        status=status.HTTP_409_CONFLICT,
                    )
                has_replied = settings_obj.stop_on_reply and EmailMessage.objects.filter(
                    user=request.user,
                    lead_id=sequence.lead_id,
                    direction='inbound',
                    received_at__gt=sequence.last_sent_at,
                ).exists()
                if has_replied or sequence.lead.status == 'blacklisted' or is_suppressed(request.user, sequence.lead.email):
                    sequence.status = 'stopped'
                else:
                    sequence.status = 'active'
                    if sequence.next_send_at <= timezone.now():
                        sequence.next_send_at = timezone.now() + timedelta(days=settings_obj.days_between)

            sequence.save(update_fields=['status', 'next_send_at', 'updated_at'])

        return Response({
            'id': sequence.id,
            'status': sequence.status,
            'next_send_at': sequence.next_send_at,
            'detail': 'Sequence updated.',
        })


class DeliverabilityView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        period = request.query_params.get('period', '30d')
        if period not in {'7d', '30d'}:
            return Response({'detail': 'Period must be 7d or 30d.'}, status=status.HTTP_400_BAD_REQUEST)
        now = timezone.now()
        start = now - timedelta(days=int(period[:-1]))
        user = request.user

        messages = EmailMessage.objects.filter(user=user, received_at__gte=start)
        totals = messages.aggregate(
            sent=Count('id', filter=Q(direction='outbound')),
            replies=Count('id', filter=Q(direction='inbound', lead__isnull=False)),
        )
        recorded_events = SuppressionEntry.objects.filter(user=user, created_at__gte=start).aggregate(
            bounces=Count('id', filter=Q(reason='bounced')),
            complaints=Count('id', filter=Q(reason='complained')),
        )
        sent = totals['sent']
        reply_rate = round(totals['replies'] * 100 / sent, 1) if sent else None
        bounce_rate = round(recorded_events['bounces'] * 100 / sent, 1) if sent else None
        today = timezone.localdate()
        senders = []
        for account in EmailAccount.objects.filter(user=user).order_by('email_address'):
            used = account.sends_today if account.sends_counted_on == today else 0
            limit = account.daily_send_limit
            remaining = max(0, limit - used) if account.is_connected else 0
            if not account.is_connected:
                mailbox_status = 'disconnected'
            elif remaining == 0:
                mailbox_status = 'limit_reached'
            elif limit and used / limit >= 0.8:
                mailbox_status = 'near_limit'
            else:
                mailbox_status = 'available'
            senders.append({
                'id': account.id,
                'email': account.email_address,
                'provider': account.get_auth_type_display(),
                'connected': account.is_connected,
                'sent_today': used,
                'daily_limit': limit,
                'remaining_today': remaining,
                'usage_percent': round(used * 100 / limit) if limit else 0,
                'status': mailbox_status,
            })

        connected = sum(1 for sender in senders if sender['connected'])
        return Response({
            'period': period,
            'from': start,
            'to': now,
            'summary': {
                'sent': sent,
                'replies': totals['replies'],
                'reply_rate': reply_rate,
                'recorded_bounces': recorded_events['bounces'],
                'recorded_bounce_rate': bounce_rate,
                'complaints': recorded_events['complaints'],
                'connected_senders': connected,
                'total_senders': len(senders),
            },
            'senders': senders,
            'data_note': 'Bounce and complaint metrics include only events recorded in your suppression list. Opens and clicks are not tracked.',
        })
