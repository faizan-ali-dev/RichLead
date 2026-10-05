"""P0-1: tenant isolation. Uniqueness must be scoped per-user, never global."""
import pytest
from django.utils import timezone

from leads.models import Lead
from inbox.models import EmailMessage


@pytest.mark.django_db
def test_two_users_can_own_the_same_lead_email(user_a, user_b):
    """The core multi-tenant guarantee: customers must not collide on shared prospects."""
    Lead.objects.create(user=user_a, name="Carol", company="Globex", niche="SaaS", email="shared@globex.test")
    Lead.objects.create(user=user_b, name="Carol", company="Globex", niche="SaaS", email="shared@globex.test")

    assert Lead.objects.filter(email="shared@globex.test").count() == 2


@pytest.mark.django_db
def test_same_user_cannot_duplicate_a_lead_email(user_a):
    from django.db import IntegrityError, transaction

    Lead.objects.create(user=user_a, name="Carol", company="Globex", niche="SaaS", email="dupe@globex.test")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Lead.objects.create(user=user_a, name="Carol2", company="Globex", niche="SaaS", email="dupe@globex.test")


@pytest.mark.django_db
def test_lead_email_is_normalised_to_lowercase(user_a):
    """Reply matching lowercases the incoming address, so storage must match."""
    lead = Lead.objects.create(user=user_a, name="Carol", company="Globex", niche="SaaS", email="Carol@Globex.TEST")
    lead.refresh_from_db()
    assert lead.email == "carol@globex.test"


@pytest.mark.django_db
def test_two_users_can_store_the_same_message_id(user_a, user_b):
    """Both parties on a thread must each keep their own copy."""
    for u in (user_a, user_b):
        EmailMessage.objects.create(
            user=u, message_id="<shared-thread@mail.test>", from_email="x@y.test",
            to_email="z@y.test", received_at=timezone.now(),
        )
    assert EmailMessage.objects.filter(message_id="<shared-thread@mail.test>").count() == 2


@pytest.mark.django_db
def test_same_user_cannot_store_duplicate_message_id(user_a):
    from django.db import IntegrityError, transaction

    EmailMessage.objects.create(
        user=user_a, message_id="<dupe@mail.test>", from_email="x@y.test",
        to_email="z@y.test", received_at=timezone.now(),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmailMessage.objects.create(
                user=user_a, message_id="<dupe@mail.test>", from_email="x@y.test",
                to_email="z@y.test", received_at=timezone.now(),
            )


@pytest.mark.django_db
def test_user_cannot_read_another_users_lead(auth_a, auth_b, user_b):
    other = Lead.objects.create(user=user_b, name="Private", company="B Corp", niche="x", email="private@b.test")
    resp = auth_a.get(f"/api/leads/{other.id}/")
    assert resp.status_code == 404
