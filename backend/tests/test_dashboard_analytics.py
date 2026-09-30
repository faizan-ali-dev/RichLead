from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from inbox.models import EmailMessage
from integrations.models import SuppressionEntry
from leads.models import AIResearch, Lead


def create_lead(user, email, name):
    return Lead.objects.create(
        user=user,
        name=name,
        company=f'{name} Company',
        niche='SaaS',
        email=email,
    )


@pytest.mark.django_db
def test_dashboard_analytics_uses_saved_events_and_is_tenant_scoped():
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username='analytics-owner',
        email='analytics-owner@example.test',
        password='Strong-test-password-123!',
        email_verified=True,
    )
    other_user = user_model.objects.create_user(
        username='analytics-other',
        email='analytics-other@example.test',
        password='Strong-test-password-456!',
        email_verified=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    now = timezone.now()
    # Anchor test emails around local noon so the assertion stays on the same
    # analytics day even when CI runs around UTC midnight.
    local_midday = timezone.make_aware(
        datetime.combine(timezone.localdate(now), time(hour=12)),
        timezone.get_current_timezone(),
    )
    lead = create_lead(user, 'prospect@example.test', 'Prospect')
    Lead.objects.filter(pk=lead.pk).update(created_at=now - timedelta(days=3))
    EmailMessage.objects.create(
        user=user,
        lead=lead,
        message_id='analytics-outbound-1',
        from_email=user.email,
        to_email=lead.email,
        received_at=local_midday - timedelta(hours=3),
        direction='outbound',
        subject='Intro',
    )
    EmailMessage.objects.create(
        user=user,
        lead=lead,
        message_id='analytics-inbound-1',
        from_email=lead.email,
        to_email=user.email,
        received_at=local_midday - timedelta(hours=2),
        direction='inbound',
        subject='Re: Intro',
    )
    research = AIResearch.objects.create(
        lead=lead,
        summary='Relevant problem',
        generated_message='A tailored message',
    )
    AIResearch.objects.filter(pk=research.pk).update(created_at=now - timedelta(days=2))
    bounce = SuppressionEntry.objects.create(
        user=user,
        email='bounced@example.test',
        reason='bounced',
    )
    SuppressionEntry.objects.filter(pk=bounce.pk).update(
        created_at=local_midday - timedelta(hours=1),
    )

    other_lead = create_lead(other_user, 'other@example.test', 'Other Tenant')
    EmailMessage.objects.create(
        user=other_user,
        lead=other_lead,
        message_id='analytics-other-outbound',
        from_email=other_user.email,
        to_email=other_lead.email,
        received_at=now - timedelta(hours=1),
        direction='outbound',
    )

    response = client.get('/api/dashboard/stats/')

    assert response.status_code == 200
    data = response.json()
    today = timezone.localdate(now).isoformat()
    today_data = next(day for day in data['analytics'] if day['date'] == today)
    assert len(data['analytics']) == 7
    assert today_data['sent'] == 1
    assert today_data['replies'] == 1
    assert today_data['bounces'] == 1
    assert [item['type'] for item in data['recent_activity'][:3]] == [
        'bounce', 'reply', 'sent',
    ]
    assert all('Other Tenant' not in item['title'] for item in data['recent_activity'])


@pytest.mark.django_db
def test_dashboard_analytics_rejects_anonymous_requests():
    response = APIClient().get('/api/dashboard/stats/')

    assert response.status_code == 401
