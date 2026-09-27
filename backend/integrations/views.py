from rest_framework import viewsets, permissions
from leads.models import Lead
from .models import APIIntegration, EmailAccount, SuppressionEntry
from .serializers import APIIntegrationSerializer, EmailAccountSerializer, SuppressionEntrySerializer


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

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .services import send_outreach_email

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def send_email_view(request):
    lead_id = request.data.get('lead_id')
    message_body = request.data.get('message')
    account_id = request.data.get('account_id')
    
    if not lead_id or not message_body:
        return Response({"error": "lead_id and message are required"}, status=status.HTTP_400_BAD_REQUEST)
        
    result = send_outreach_email(lead_id, request.user, message_body, account_id)
    
    if result.get('success'):
        return Response(result, status=status.HTTP_200_OK)
    else:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)

from django.http import HttpResponse
from rest_framework.permissions import AllowAny
from .unsubscribe import resolve_token


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


from .apollo_service import fetch_apollo_leads

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def apollo_prospect_view(request):
    search_params = request.data.get('search_params', {})
    
    result = fetch_apollo_leads(request.user, search_params)
    
    if result.get('success'):
        return Response(result, status=status.HTTP_200_OK)
    else:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
