from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import PromptTemplate
from .serializers import PromptTemplateSerializer
from .services import generate_outreach_message
from leads.models import Lead

class PromptTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PromptTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PromptTemplate.objects.filter(user=self.request.user)

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def process_lead(request):
    """
    Triggers the AI engine for a specific lead ID.
    Expected JSON: {"lead_id": 1}
    """
    lead_id = request.data.get('lead_id')
    if not lead_id:
        return Response({"error": "lead_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        
    result = generate_outreach_message(lead_id, request.user)
    
    if result.get('success'):
        return Response(result, status=status.HTTP_200_OK)
    else:
        return Response(result, status=status.HTTP_400_BAD_REQUEST)
