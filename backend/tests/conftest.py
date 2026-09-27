import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user_a(db):
    return User.objects.create_user(username="alice", email="alice@acme.test", password="Str0ng!Pass2026")


@pytest.fixture
def user_b(db):
    return User.objects.create_user(username="bob", email="bob@acme.test", password="Str0ng!Pass2026")


@pytest.fixture
def auth_a(api, user_a):
    api.force_authenticate(user=user_a)
    return api


@pytest.fixture
def auth_b(user_b):
    client = APIClient()
    client.force_authenticate(user=user_b)
    return client


@pytest.fixture
def lead_a(db, user_a):
    from leads.models import Lead
    return Lead.objects.create(
        user=user_a, name="Carol", company="Globex", niche="SaaS", email="carol@globex.test"
    )
