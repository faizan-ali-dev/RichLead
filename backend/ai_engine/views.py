from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle


class AIGenerationThrottle(UserRateThrottle):
    """Each call spends the tenant's own LLM quota; cap it independently."""
    scope = 'ai'
from .models import PromptTemplate
from .serializers import PromptTemplateSerializer
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
    try:
        lead_id = int(lead_id)
    except (TypeError, ValueError):
        return Response({"error": "lead_id must be an integer."}, status=status.HTTP_400_BAD_REQUEST)
    if not Lead.objects.filter(id=lead_id, user=request.user).exists():
        return Response({"error": "Lead not found."}, status=status.HTTP_404_NOT_FOUND)

    from async_jobs.views import queue_job_response
    return queue_job_response(request, 'generate_draft', {'lead_id': lead_id})


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

    icp_fields = {
        'icp_titles', 'icp_industries', 'icp_locations',
        'icp_employee_min', 'icp_employee_max', 'icp_requires_funding',
    }
    icp_changed = bool(icp_fields & set(serializer.validated_data))
    profile = serializer.save()

    # Re-rank pending leads when the targeting criteria change. Small tenants are
    # fine inline; a large book is capped so the request stays snappy.
    rescored = None
    if icp_changed:
        from .scoring import rescore_user_leads
        from leads.models import Lead

        if Lead.objects.filter(user=request.user, status='pending').count() <= 500:
            rescored = rescore_user_leads(request.user, profile)

    data = BusinessProfileSerializer(profile).data
    if rescored is not None:
        data['rescored_leads'] = rescored
    return Response(data)


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
    settings_obj = serializer.save()
    if not settings_obj.enabled or settings_obj.total_follow_ups == 0:
        from integrations.models import FollowUpSequence
        FollowUpSequence.objects.filter(user=request.user, status='active').update(
            status='completed', claim_token=None, claim_expires_at=None,
            prepared_subject='', prepared_body='',
        )
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
    from async_jobs.views import queue_job_response

    limit = request.data.get('limit')
    try:
        limit = int(limit) if limit is not None else None
    except (TypeError, ValueError):
        limit = None

    if limit is not None:
        limit = max(1, min(limit, 50))
    return queue_job_response(request, 'draft_queue', {'limit': limit})


@api_view(['GET', 'PATCH', 'PUT'])
@permission_classes([permissions.IsAuthenticated])
def subject_experiment_view(request):
    """Subject-line A/B test configuration and live results."""
    from .experiments import SubjectExperiment, evaluate_experiment
    from .serializers import SubjectExperimentSerializer

    experiment, _ = SubjectExperiment.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        # Opportunistically check whether the data now supports a decision.
        evaluate_experiment(request.user, experiment)
        experiment.refresh_from_db()
        return Response(SubjectExperimentSerializer(experiment).data)

    serializer = SubjectExperimentSerializer(experiment, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    experiment = serializer.save()
    # Re-running a decided experiment clears the prior verdict.
    if experiment.status == 'running' and experiment.winner:
        experiment.winner = ''
        experiment.decided_at = None
        experiment.save(update_fields=['winner', 'decided_at', 'updated_at'])
    return Response(SubjectExperimentSerializer(experiment).data)
