"""LLM configuration endpoints.

Flow the settings UI drives:

    GET  llm/catalog/   -> providers + curated models (no key needed)
    POST llm/models/    -> live model list for a provider, given a key
    POST llm/validate/  -> one real generation round-trip, save nothing
    POST llm/connect/   -> validate, then persist only if it worked
    GET  llm/active/    -> which LLM every AI feature is currently using
    POST llm/primary/   -> switch the active LLM
    DELETE llm/<provider>/ -> remove a stored key
"""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from integrations.models import APIIntegration
from . import providers

logger = logging.getLogger(__name__)


class LLMSetupThrottle(UserRateThrottle):
    """Validation spends the tenant's own quota and hits a third party."""
    scope = 'ai'


def _serialize(integration):
    return {
        'id': integration.id,
        'provider': integration.provider,
        'provider_label': providers.PROVIDER_CATALOG.get(integration.provider, {}).get('label', integration.provider),
        'model': integration.model,
        'is_primary': integration.is_primary,
        'is_active': integration.is_active,
        'last_validated_at': integration.last_validated_at,
        'created_at': integration.created_at,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def llm_catalog(request):
    """Providers and their curated models. Safe to call before a key exists."""
    configured = {
        i.provider: _serialize(i)
        for i in APIIntegration.objects.filter(user=request.user, provider__in=providers.SUPPORTED_PROVIDERS)
    }
    return Response({'providers': providers.catalog(), 'configured': configured})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMSetupThrottle])
def llm_models(request):
    """Live model list for a provider.

    Accepts either a new `api_key`, or `use_saved` to reuse the stored one so the
    user doesn't have to paste the key again to change model.
    """
    provider = request.data.get('provider')
    api_key = request.data.get('api_key') or ''

    if provider not in providers.SUPPORTED_PROVIDERS:
        return Response({'error': 'Select a supported provider.'}, status=status.HTTP_400_BAD_REQUEST)

    if not api_key:
        existing = APIIntegration.objects.filter(user=request.user, provider=provider).first()
        if not existing:
            return Response({'error': 'API key is required.'}, status=status.HTTP_400_BAD_REQUEST)
        api_key = existing.get_api_key()

    try:
        models = providers.list_models(provider, api_key)
    except providers.ProviderError as exc:
        return Response({'error': exc.message}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'provider': provider, 'models': models})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMSetupThrottle])
def llm_validate(request):
    """Test a provider/key/model combination without saving anything."""
    provider = request.data.get('provider')
    model = request.data.get('model')
    api_key = request.data.get('api_key') or ''

    if not api_key:
        existing = APIIntegration.objects.filter(user=request.user, provider=provider).first()
        api_key = existing.get_api_key() if existing else ''

    ok, error = providers.validate(provider, api_key, model)
    if not ok:
        return Response({'success': False, 'error': error}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'success': True, 'message': f'{model} responded successfully.'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([LLMSetupThrottle])
def llm_connect(request):
    """Validate, then persist only on success.

    A key is never written to the database until a real generation call with it
    has succeeded -- a saved-but-broken integration would fail later, mid-campaign,
    where the error is far harder to connect back to a bad key.
    """
    provider = request.data.get('provider')
    model = request.data.get('model')
    api_key = request.data.get('api_key') or ''
    make_primary = request.data.get('make_primary', True)

    if provider not in providers.SUPPORTED_PROVIDERS:
        return Response({'success': False, 'error': 'Select a supported provider.'},
                        status=status.HTTP_400_BAD_REQUEST)

    existing = APIIntegration.objects.filter(user=request.user, provider=provider).first()
    if not api_key:
        if not existing:
            return Response({'success': False, 'error': 'API key is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        api_key = existing.get_api_key()

    ok, error = providers.validate(provider, api_key, model)
    if not ok:
        return Response({'success': False, 'error': error}, status=status.HTTP_400_BAD_REQUEST)

    integration = existing or APIIntegration(user=request.user, provider=provider)
    integration.set_api_key(api_key)
    integration.model = model
    integration.is_active = True
    integration.last_validated_at = timezone.now()
    integration.save()

    if make_primary:
        integration.make_primary()

    logger.info('Connected %s/%s for user %s', provider, model, request.user.id)
    return Response({'success': True, 'integration': _serialize(integration)},
                    status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def llm_active(request):
    """The LLM every AI feature will use, or null if none is configured."""
    from .services import get_active_llm

    active = get_active_llm(request.user)
    return Response({'active': _serialize(active) if active else None})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def llm_set_primary(request):
    provider = request.data.get('provider')
    integration = APIIntegration.objects.filter(user=request.user, provider=provider).first()
    if not integration:
        return Response({'error': 'That provider is not connected.'}, status=status.HTTP_404_NOT_FOUND)

    integration.make_primary()
    return Response({'success': True, 'integration': _serialize(integration)})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def llm_disconnect(request, provider):
    integration = APIIntegration.objects.filter(user=request.user, provider=provider).first()
    if not integration:
        return Response({'error': 'That provider is not connected.'}, status=status.HTTP_404_NOT_FOUND)

    was_primary = integration.is_primary
    integration.delete()

    # Don't leave the tenant with keys but no active LLM.
    if was_primary:
        fallback = APIIntegration.objects.filter(
            user=request.user, provider__in=providers.SUPPORTED_PROVIDERS, is_active=True,
        ).exclude(model='').first()
        if fallback:
            fallback.make_primary()

    return Response({'success': True})
