from datetime import timedelta

import pytest
from django.utils import timezone

from inbox.models import EmailMessage
from integrations.models import EmailAccount, FollowUpSequence, SuppressionEntry
from leads.models import Lead


@pytest.mark.django_db
def test_followup_sequence_controls_are_scoped_and_pause_resume_stop(auth_a, auth_b, user_a, user_b, lead_a):
    other_lead = Lead.objects.create(
        user=user_b, name='Other', company='Other Co', niche='SaaS', email='other@example.test',
    )
    now = timezone.now()
    own_sequence = FollowUpSequence.objects.create(
        user=user_a, lead=lead_a, next_send_at=now + timedelta(days=1), last_sent_at=now,
    )
    other_sequence = FollowUpSequence.objects.create(
        user=user_b, lead=other_lead, next_send_at=now + timedelta(days=1), last_sent_at=now,
    )

    listing = auth_a.get('/api/integrations/sequences/')
    assert listing.status_code == 200
    assert listing.data['counts']['active'] == 1
    assert [row['id'] for row in listing.data['items']] == [own_sequence.id]

    assert auth_a.post(f'/api/integrations/sequences/{other_sequence.id}/', {'action': 'stop'}).status_code == 404
    paused = auth_a.post(f'/api/integrations/sequences/{own_sequence.id}/', {'action': 'pause'})
    assert paused.status_code == 200
    assert paused.data['status'] == 'paused'

    resumed = auth_a.post(f'/api/integrations/sequences/{own_sequence.id}/', {'action': 'resume'})
    assert resumed.status_code == 200
    assert resumed.data['status'] == 'active'

    stopped = auth_a.post(f'/api/integrations/sequences/{own_sequence.id}/', {'action': 'stop'})
    assert stopped.status_code == 200
    assert stopped.data['status'] == 'stopped'


@pytest.mark.django_db
def test_paused_sequence_cannot_resume_after_reply(auth_a, user_a, lead_a):
    now = timezone.now()
    sequence = FollowUpSequence.objects.create(
        user=user_a, lead=lead_a, status='paused',
        next_send_at=now - timedelta(days=1), last_sent_at=now - timedelta(hours=2),
    )
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, message_id='resume-after-reply', direction='inbound',
        from_email=lead_a.email, to_email=user_a.email, body_text='Thanks', received_at=now,
    )

    response = auth_a.post(f'/api/integrations/sequences/{sequence.id}/', {'action': 'resume'})

    assert response.status_code == 200
    assert response.data['status'] == 'stopped'


@pytest.mark.django_db
def test_deliverability_uses_recorded_mail_events_and_sender_daily_limits(auth_a, user_a, lead_a):
    now = timezone.now()
    account = EmailAccount.objects.create(
        user=user_a, email_address='sales@example.test', provider='smtp', is_connected=True,
        sends_counted_on=timezone.localdate(), sends_today=8, daily_send_limit=10,
    )
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, account=account, message_id='health-out', direction='outbound',
        from_email=account.email_address, to_email=lead_a.email, body_text='Hello', received_at=now,
    )
    EmailMessage.objects.create(
        user=user_a, lead=lead_a, account=account, message_id='health-in', direction='inbound',
        from_email=lead_a.email, to_email=account.email_address, body_text='Thanks', received_at=now,
    )
    SuppressionEntry.objects.create(user=user_a, email='bounced@example.test', reason='bounced')

    response = auth_a.get('/api/integrations/deliverability/?period=7d')

    assert response.status_code == 200
    assert response.data['summary']['sent'] == 1
    assert response.data['summary']['replies'] == 1
    assert response.data['summary']['reply_rate'] == 100
    assert response.data['summary']['recorded_bounces'] == 1
    assert response.data['senders'][0]['remaining_today'] == 2
    assert response.data['senders'][0]['status'] == 'near_limit'


@pytest.mark.django_db
def test_lead_quality_marks_provider_verified_and_suppressed_leads(auth_a, user_a, lead_a):
    lead_a.email_status = 'verified'
    lead_a.title = 'Founder'
    lead_a.website = 'globex.test'
    lead_a.icp_score = 91
    lead_a.save()
    suppressed = Lead.objects.create(
        user=user_a, name='Suppressed', company='Example', title='Owner', niche='SaaS',
        email='blocked@example.test', email_status='verified', website='example.test', icp_score=90,
    )
    SuppressionEntry.objects.create(user=user_a, email=suppressed.email, reason='manual')

    response = auth_a.get('/api/lead-quality/')

    assert response.status_code == 200
    assert response.data['summary']['total'] == 2
    assert response.data['summary']['verified'] == 2
    assert response.data['summary']['suppressed'] == 1
    assert response.data['summary']['ready_to_contact'] == 1
    flagged = next(row for row in response.data['attention_leads'] if row['id'] == suppressed.id)
    assert 'Suppressed, do not contact' in flagged['flags']


@pytest.mark.django_db
def test_workspace_insights_require_authentication(api):
    assert api.get('/api/integrations/sequences/').status_code == 401
    assert api.get('/api/integrations/deliverability/').status_code == 401
    assert api.get('/api/lead-quality/').status_code == 401


@pytest.mark.django_db
def test_manual_lead_cannot_claim_provider_email_verification(auth_a):
    response = auth_a.post('/api/leads/', {
        'name': 'Manual Contact',
        'company': 'Example Co',
        'niche': 'SaaS',
        'email': 'manual@example.test',
        'email_status': 'verified',
    }, format='json')

    assert response.status_code == 201
    assert response.data['email_status'] == 'unknown'
