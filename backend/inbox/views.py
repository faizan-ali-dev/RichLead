import re

from django.db.models import Count
from rest_framework import views, status, serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import EmailMessage
from .email_body import reply_preview, strip_quoted_reply
from .services import deduplicate_outbound_echoes, html_to_text
from .sanitization import sanitize_email_html
from async_jobs.views import queue_job_response
from leads.models import Lead
from django.utils.html import linebreaks

class EmailMessageSerializer(serializers.ModelSerializer):
    body_text = serializers.SerializerMethodField()
    body_html = serializers.SerializerMethodField()
    account_email = serializers.SerializerMethodField()

    class Meta:
        model = EmailMessage
        fields = ['id', 'subject', 'from_email', 'to_email', 'body_text', 'body_html', 'received_at', 'direction', 'is_read', 'account_email']

    def get_body_html(self, obj):
        if obj.direction == 'inbound':
            body = strip_quoted_reply(obj.body_text or html_to_text(obj.body_html))
            return linebreaks(body) if body else ''
        return sanitize_email_html(obj.body_html)

    def get_body_text(self, obj):
        if obj.direction == 'inbound':
            return strip_quoted_reply(obj.body_text or html_to_text(obj.body_html))
        return obj.body_text

    def get_account_email(self, obj):
        return obj.account.email_address if obj.account_id else None

class InboxListView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # select_related('lead') collapses what was one extra query per message.
        messages = list(
            EmailMessage.objects.filter(user=request.user)
            .select_related('lead', 'account')
            .exclude(lead__isnull=True)
            .order_by('-received_at')
        )
        messages = deduplicate_outbound_echoes(messages)

        # Group by lead
        threads = {}
        for msg in messages:
            if not msg.lead:
                continue
            
            lead_id = msg.lead.id
            if lead_id not in threads:
                threads[lead_id] = {
                    'lead_id': lead_id,
                    'lead_name': msg.lead.name,
                    'lead_company': msg.lead.company,
                    'lead_email': msg.lead.email,
                    'message_count': 0,
                    'unread_count': 0,
                    'mailbox_email': None,
                    '_sent_mailbox_found': False,
                    'messages': []
                }

            thread = threads[lead_id]
            message_data = EmailMessageSerializer(msg).data
            thread['messages'].append(message_data)
            thread['message_count'] += 1
            if msg.direction == 'inbound' and not msg.is_read:
                thread['unread_count'] += 1
            if thread['mailbox_email'] is None and message_data['account_email']:
                thread['mailbox_email'] = message_data['account_email']
            if msg.direction == 'outbound' and message_data['account_email'] and not thread['_sent_mailbox_found']:
                thread['mailbox_email'] = message_data['account_email']
                thread['_sent_mailbox_found'] = True
            
        for thread in threads.values():
            thread.pop('_sent_mailbox_found', None)
            previous_outbound = {}
            for message in reversed(thread['messages']):
                if message['direction'] == 'outbound':
                    subject_key = re.sub(r'^(?:(?:re|fw|fwd)\s*:\s*)+', '', message['subject'] or '', flags=re.IGNORECASE).strip().casefold()
                    if message['body_text']:
                        previous_outbound[subject_key] = message['body_text']
                    continue

                if not re.match(r'^\s*re\s*:', message['subject'] or '', re.IGNORECASE):
                    continue
                subject_key = re.sub(r'^(?:(?:re|fw|fwd)\s*:\s*)+', '', message['subject'] or '', flags=re.IGNORECASE).strip().casefold()
                original = previous_outbound.get(subject_key)
                if original:
                    message['reply_to_preview'] = reply_preview(original)

        return Response(list(threads.values()))


class InboxNotificationsView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread = EmailMessage.objects.filter(
            user=request.user,
            direction='inbound',
            is_read=False,
            lead__isnull=False,
        )
        total_unread = unread.count()
        latest_unread = list(
            unread.select_related('lead', 'account').order_by('-received_at')[:50]
        )
        lead_ids = {message.lead_id for message in latest_unread}
        counts = dict(
            unread.filter(lead_id__in=lead_ids)
            .values('lead_id')
            .annotate(total=Count('id'))
            .values_list('lead_id', 'total')
        )
        notifications = []
        seen_leads = set()
        for message in latest_unread:
            if message.lead_id in seen_leads:
                continue
            seen_leads.add(message.lead_id)
            notifications.append({
                'id': message.id,
                'lead_id': message.lead_id,
                'lead_name': message.lead.name,
                'lead_email': message.lead.email,
                'subject': message.subject or 'No subject',
                'preview': strip_quoted_reply(message.body_text).strip()[:180],
                'received_at': message.received_at,
                'account_email': message.account.email_address if message.account_id else None,
                'unread_count': counts.get(message.lead_id, 1),
            })

        return Response({'unread_count': total_unread, 'notifications': notifications[:20]})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_thread_read(request, lead_id):
    if not Lead.objects.filter(pk=lead_id, user=request.user).exists():
        return Response({'error': 'Conversation not found.'}, status=status.HTTP_404_NOT_FOUND)
    updated = EmailMessage.objects.filter(
        user=request.user,
        lead_id=lead_id,
        direction='inbound',
        is_read=False,
    ).update(is_read=True)
    return Response({'marked_read': updated})

class InboxSyncView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        return queue_job_response(request, 'inbox_sync', {})
