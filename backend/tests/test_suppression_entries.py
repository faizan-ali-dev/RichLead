import pytest

from integrations.models import SuppressionEntry, is_suppressed


@pytest.mark.django_db
def test_user_can_add_multiple_domain_suppressions_and_readd_idempotently(auth_a, user_a):
    first = auth_a.post(
        '/api/integrations/suppression/',
        {'domain': 'example.com', 'reason': 'manual'},
        format='json',
    )
    second = auth_a.post(
        '/api/integrations/suppression/',
        {'domain': 'microsoft.com', 'reason': 'manual'},
        format='json',
    )
    repeated = auth_a.post(
        '/api/integrations/suppression/',
        {'domain': 'MICROSOFT.COM', 'reason': 'manual'},
        format='json',
    )

    assert first.status_code == second.status_code == repeated.status_code == 201
    assert SuppressionEntry.objects.filter(user=user_a, email='').count() == 2
    assert SuppressionEntry.objects.filter(user=user_a, domain='microsoft.com').count() == 1
    assert is_suppressed(user_a, 'person@microsoft.com')


@pytest.mark.django_db
def test_email_suppression_remains_unique_and_independent_from_domain_entries(auth_a, user_a):
    domain = auth_a.post(
        '/api/integrations/suppression/',
        {'domain': 'example.com'},
        format='json',
    )
    email = auth_a.post(
        '/api/integrations/suppression/',
        {'email': 'Blocked@Example.com'},
        format='json',
    )
    repeated_email = auth_a.post(
        '/api/integrations/suppression/',
        {'email': 'blocked@example.com'},
        format='json',
    )

    assert domain.status_code == email.status_code == repeated_email.status_code == 201
    assert SuppressionEntry.objects.filter(user=user_a, email='blocked@example.com').count() == 1
    assert is_suppressed(user_a, 'blocked@example.com')


@pytest.mark.django_db
def test_suppression_rejects_invalid_or_ambiguous_entries(auth_a):
    invalid_domain = auth_a.post(
        '/api/integrations/suppression/', {'domain': 'https://example.com'}, format='json',
    )
    ambiguous = auth_a.post(
        '/api/integrations/suppression/',
        {'email': 'blocked@example.com', 'domain': 'example.com'},
        format='json',
    )

    assert invalid_domain.status_code == 400
    assert ambiguous.status_code == 400
