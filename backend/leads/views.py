from django.db.models import Count, Q
from rest_framework import viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Lead
from .serializers import LeadSerializer

class LeadViewSet(viewsets.ModelViewSet):
    serializer_class = LeadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # The serializer walks score_breakdowns, intent_signals and research for every
        # row; without prefetching that is 3 extra queries per lead.
        return (
            Lead.objects.filter(user=self.request.user)
            .select_related('research')
            .prefetch_related('score_breakdowns', 'intent_signals')
            .order_by('-id')
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_stats(request):
    """Tenant dashboard counters, computed in a single aggregate pass.

    Sends and replies come from event timestamps rather than `status`: a lead that
    replies is still a lead that was sent to, and must stay in the denominator.
    """
    stats = Lead.objects.filter(user=request.user).aggregate(
        leads_discovered=Count('id'),
        qualified=Count('id', filter=Q(icp_score__gt=80)),
        ai_researched=Count('id', filter=Q(research__isnull=False)),
        messages_generated=Count(
            'id',
            filter=Q(research__isnull=False) & ~Q(research__generated_message=''),
        ),
        pending_review=Count('id', filter=Q(status='pending')),
        messages_sent=Count('id', filter=Q(first_sent_at__isnull=False)),
        replies=Count('id', filter=Q(replied_at__isnull=False)),
    )

    sent = stats['messages_sent']
    reply_rate = round((stats['replies'] / sent * 100) if sent else 0.0, 1)

    return Response({**stats, "reply_rate": f"{reply_rate}%"})
