"""Baseline: the harness itself works and the app boots."""
import pytest


def test_settings_load():
    from django.conf import settings
    assert settings.AUTH_USER_MODEL == "users.User"


@pytest.mark.django_db
def test_user_fixture(user_a):
    assert user_a.pk is not None


def test_auth_required_without_token(api):
    resp = api.get("/api/leads/")
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_authenticated_leads_list(auth_a):
    resp = auth_a.get("/api/leads/")
    assert resp.status_code == 200
