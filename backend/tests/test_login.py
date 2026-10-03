from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from admin_dashboard.models import LoginActivity


def test_login_accepts_username(db):
    user = get_user_model().objects.create_user(
        username="login-user", email="login@example.test", password="Strong-password-427!", email_verified=True,
    )

    response = APIClient().post(
        "/api/token/",
        {"username": user.username, "password": "Strong-password-427!"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["refresh"]
    assert LoginActivity.objects.filter(user=user).count() == 1


def test_login_accepts_case_insensitive_email(db):
    user = get_user_model().objects.create_user(
        username="email-login-user", email="login@example.test", password="Strong-password-427!", email_verified=True,
    )

    response = APIClient().post(
        "/api/token/",
        {"username": "LOGIN@EXAMPLE.TEST", "password": "Strong-password-427!"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["refresh"]
    assert LoginActivity.objects.filter(user=user).count() == 1


def test_login_rejects_unverified_email(db):
    user = get_user_model().objects.create_user(
        username="unverified-user", email="unverified@example.test", password="Strong-password-427!",
    )

    response = APIClient().post(
        "/api/token/",
        {"username": user.username, "password": "Strong-password-427!"},
        format="json",
    )

    assert response.status_code == 401
    assert "verify" in str(response.data["detail"]).lower()
    assert not LoginActivity.objects.filter(user=user).exists()
