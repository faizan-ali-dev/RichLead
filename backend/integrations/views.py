from django.http import HttpResponse
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from async_jobs.views import queue_job_response
from leads.models import Lead
from .models import APIIntegration, EmailAccount, SuppressionEntry
from .serializers import APIIntegrationSerializer, EmailAccountSerializer, SuppressionEntrySerializer
from .unsubscribe import resolve_token


class SuppressionEntryViewSet(viewsets.ModelViewSet):
    serializer_class = SuppressionEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SuppressionEntry.objects.filter(user=self.request.user).order_by('-created_at')

class APIIntegrationViewSet(viewsets.ModelViewSet):
    serializer_class = APIIntegrationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return APIIntegration.objects.filter(user=self.request.user)

class EmailAccountViewSet(viewsets.ModelViewSet):
    serializer_class = EmailAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return EmailAccount.objects.filter(user=self.request.user)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_email_view(request):
    lead_id = request.data.get('lead_id')
    message_body = request.data.get('message')
    account_id = request.data.get('account_id')
    
    if not lead_id or not isinstance(message_body, str) or not message_body.strip():
        return Response({"error": "lead_id and message are required"}, status=status.HTTP_400_BAD_REQUEST)
    if len(message_body) > 20000:
        return Response({"error": "message must be 20,000 characters or fewer."}, status=status.HTTP_400_BAD_REQUEST)
    subject = request.data.get('subject')
    if subject is not None and (not isinstance(subject, str) or len(subject) > 255):
        return Response({"error": "subject must be a string of 255 characters or fewer."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        lead_id = int(lead_id)
    except (TypeError, ValueError):
        return Response({"error": "lead_id must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
    if not Lead.objects.filter(id=lead_id, user=request.user).exists():
        return Response({"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND)

    return queue_job_response(request, 'send_email', {
        'lead_id': lead_id,
        'message': message_body,
        'account_id': account_id,
        'subject': subject,
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_email_batch_view(request):
    items = request.data.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 50:
        return Response({'error': 'items must contain between 1 and 50 emails.'}, status=status.HTTP_400_BAD_REQUEST)

    normalized = []
    lead_ids = set()
    for item in items:
        if not isinstance(item, dict):
            return Response({'error': 'Each item must be an object.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            lead_id = int(item.get('lead_id'))
        except (TypeError, ValueError):
            return Response({'error': 'Every item must include an integer lead_id.'}, status=status.HTTP_400_BAD_REQUEST)
        message = item.get('message')
        if not isinstance(message, str) or not message.strip() or len(message) > 20000:
            return Response({'error': 'Every item must include a message of 1 to 20,000 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        subject = item.get('subject')
        if subject is not None and (not isinstance(subject, str) or len(subject) > 255):
            return Response({'error': 'Each subject must be a string of 255 characters or fewer.'}, status=status.HTTP_400_BAD_REQUEST)
        lead_ids.add(lead_id)
        normalized.append({
            'lead_id': lead_id,
            'message': message,
            'account_id': item.get('account_id'),
            'subject': subject,
        })

    owned_ids = set(Lead.objects.filter(user=request.user, id__in=lead_ids).values_list('id', flat=True))
    if owned_ids != lead_ids:
        return Response({'error': 'One or more leads were not found.'}, status=status.HTTP_404_NOT_FOUND)
    if len(lead_ids) != len(normalized):
        return Response({'error': 'A lead may only appear once in a batch.'}, status=status.HTTP_400_BAD_REQUEST)

    return queue_job_response(request, 'send_email_batch', {'items': normalized})

@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def unsubscribe_view(request, token):
    """One-click unsubscribe. Public by necessity -- recipients have no account.

    Authorisation comes from the signature on the token, not from a session.
    """
    resolved = resolve_token(token)
    if not resolved:
        return HttpResponse("This unsubscribe link is invalid.", status=400, content_type="text/plain")

    user_id, lead_id = resolved
    lead = Lead.objects.filter(id=lead_id, user_id=user_id).first()
    if not lead:
        return HttpResponse("You have been unsubscribed.", content_type="text/plain")

    SuppressionEntry.objects.get_or_create(
        user_id=user_id,
        email=lead.email,
        defaults={'reason': 'unsubscribed', 'note': 'One-click unsubscribe'},
    )
    if lead.status != 'blacklisted':
        lead.status = 'blacklisted'
        lead.save(update_fields=['status'])

    return HttpResponse(
        "You have been unsubscribed and will not receive further emails.",
        content_type="text/plain",
    )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def apollo_prospect_view(request):
    search_params = request.data.get('search_params', {})
    if not isinstance(search_params, dict):
        return Response({'error': 'search_params must be an object.'}, status=status.HTTP_400_BAD_REQUEST)
    return queue_job_response(request, 'apollo_search', {'search_params': search_params})


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def hunter_prospect_view(request):
    search_params = request.data.get('search_params', {})
    if not isinstance(search_params, dict):
        return Response({'error': 'search_params must be an object.'}, status=status.HTTP_400_BAD_REQUEST)
    return queue_job_response(request, 'hunter_search', {'search_params': search_params})
