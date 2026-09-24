from rest_framework import views, status, serializers
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import EmailMessage
from .services import sync_emails_for_user

class EmailMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMessage
        fields = ['id', 'subject', 'from_email', 'to_email', 'body_text', 'body_html', 'received_at', 'direction', 'is_read']

class InboxListView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        messages = EmailMessage.objects.filter(user=request.user).order_by('-received_at')
        
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
                    'messages': []
                }
            
            threads[lead_id]['messages'].append(EmailMessageSerializer(msg).data)
            
        return Response(list(threads.values()))

class InboxSyncView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = sync_emails_for_user(request.user)
        return Response(result)
