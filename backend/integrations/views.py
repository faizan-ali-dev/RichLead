from rest_framework import viewsets, permissions
from .models import APIIntegration, EmailAccount
from .serializers import APIIntegrationSerializer, EmailAccountSerializer

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
