"""
URL configuration for richlead_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed


class UsernameOrEmailTokenSerializer(TokenObtainPairSerializer):
    """Accept either the account username or its email in the login field."""

    def validate(self, attrs):
        identifier = attrs.get(self.username_field, "").strip()
        user_model = get_user_model()
        username_matches = user_model.objects.filter(**{self.username_field: identifier})
        if not username_matches.exists():
            # Registration enforces unique email addresses case-insensitively.
            # Keep email lookup case-insensitive so users can type it naturally.
            email_matches = user_model.objects.filter(email__iexact=identifier)
            if email_matches.count() == 1:
                attrs[self.username_field] = email_matches.get().get_username()
        data = super().validate(attrs)
        if not self.user.email_verified:
            raise AuthenticationFailed('Please verify your email before signing in.')
        return data


class ThrottledTokenObtainPairView(TokenObtainPairView):
    """Token issuance is the brute-force surface; rate-limit it by IP."""
    throttle_scope = 'login'
    serializer_class = UsernameOrEmailTokenSerializer


class ThrottledTokenRefreshView(TokenRefreshView):
    throttle_scope = 'login'


def health(_request):
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', health, name='health'),
    path('api/token/', ThrottledTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', ThrottledTokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),
    path('api/users/', include('users.urls')),
    path('api/', include('leads.urls')),
    path('api/integrations/', include('integrations.urls')),
    path('api/ai/', include('ai_engine.urls')),
    path('api/inbox/', include('inbox.urls')),
]
