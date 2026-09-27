from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


class AIGenerationThrottle(UserRateThrottle):
    """Each call spends the tenant's own LLM quota; cap it independently."""
    scope = 'ai'
from .models import PromptTemplate
from .serializers import PromptTemplateSerializer
from .services import generate_outreach_message
from leads.models import Lead

class PromptTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = PromptTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PromptTemplate.objects.filter(user=self.request.user).order_by('-is_active', '-updated_at')


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def prompt_rules_view(request):
    """The rules applied to every generation, shown read-only in settings.

    Surfaced rather than hidden so users understand why their output is
    constrained, and so "why did it ignore my prompt" has a visible answer.
    """
    from .prompt_rules import (
        FORMATTING_RULES, HUMAN_VOICE_RULES, STRUCTURE_RULES, SUBJECT_RULES,
        PRIMARY_TAB_RULES,
    )

    return Response({
        'editable': False,
        'explanation': (
            'These are appended to every generation after your own instructions and cannot be '
            'turned off. They exist because removing them does not change the writing style, it '
            'sends the mail to spam.'
        ),
        'sections': [
            {'title': 'Formatting', 'rules': FORMATTING_RULES},
            {'title': 'Human voice', 'rules': HUMAN_VOICE_RULES},
            {'title': 'Structure', 'rules': STRUCTURE_RULES},
            {'title': 'Primary tab (not Promotions)', 'rules': PRIMARY_TAB_RULES},
            {'title': 'Subject line', 'rules': SUBJECT_RULES},
        ],
    })


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def spam_check_view(request):
    """Score an arbitrary subject/body for spam and for Promotions-tab risk.

    Two separate scores because they are two separate problems: a message can
    pass every spam filter and still be filed under Promotions.
    """
    from .prompt_rules import lint_email, analyze_promotions_risk

    subject = request.data.get('subject', '')
    body = request.data.get('body', '')

    return Response({
        **lint_email(subject, body),
        'promotions': analyze_promotions_risk(
            subject, body,
            has_unsubscribe_header=request.user.unsubscribe_mode in ('header', 'both'),
        ),
    })

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AIGenerationThrottle])
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


@api_view(['GET', 'PATCH', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
def business_profile_view(request):
    """The tenant's business profile, created on first access."""
    from .models import BusinessProfile
    from .serializers import BusinessProfileSerializer

    profile, _ = BusinessProfile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return Response(BusinessProfileSerializer(profile).data)

    serializer = BusinessProfileSerializer(profile, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['GET', 'PATCH', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
def followup_settings_view(request):
    """Follow-up count and spacing, created on first access."""
    from .models import FollowUpSettings
    from .serializers import FollowUpSettingsSerializer

    settings_obj, _ = FollowUpSettings.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return Response(FollowUpSettingsSerializer(settings_obj).data)

    serializer = FollowUpSettingsSerializer(settings_obj, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([AIGenerationThrottle])
def draft_queue_view(request):
    """Draft every pending lead that doesn't have one yet.

    The review queue exists for approving copy, not for triggering generation one
    lead at a time. This fills the queue so the reviewer opens it and finds
    finished emails waiting.
    """
    from .services import draft_pending_leads

    limit = request.data.get('limit')
    try:
        limit = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        limit = None

    result = draft_pending_leads(request.user, limit=limit)
    status_code = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
    return Response(result, status=status_code)
