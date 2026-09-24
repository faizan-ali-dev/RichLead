from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Lead
from .serializers import LeadSerializer

class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Lead.objects.filter(user=self.request.user).order_by('-id')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    user_leads = Lead.objects.filter(user=request.user)
    
    total_leads = user_leads.count()
    qualified = user_leads.filter(icp_score__gt=80).count()
    researched = user_leads.filter(research__isnull=False).count()
    messages_generated = user_leads.filter(research__generated_message__isnull=False).count()
    pending_review = user_leads.filter(status='pending').count()
    messages_sent = user_leads.filter(status='reached').count()
    replies = user_leads.filter(status='replied').count()
    
    reply_rate = round((replies / messages_sent * 100) if messages_sent > 0 else 0, 1)

    return Response({
        "leads_discovered": total_leads,
        "qualified": qualified,
        "ai_researched": researched,
        "messages_generated": messages_generated,
        "pending_review": pending_review,
        "messages_sent": messages_sent,
        "reply_rate": f"{reply_rate}%"
    })
