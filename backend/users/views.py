import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle

from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserRegistrationSerializer,
)

logger = logging.getLogger(__name__)


class PasswordResetRequestThrottle(AnonRateThrottle):
    scope = 'password_reset'


class PasswordResetConfirmThrottle(AnonRateThrottle):
    scope = 'password_reset_confirm'

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    user = request.user
    if request.method == 'GET':
        return Response({
            'autopilot_active': user.autopilot_active,
            'username': user.username,
            'email': user.email,
            'unsubscribe_mode': user.unsubscribe_mode,
            'unsubscribe_text': user.unsubscribe_text,
        })
    elif request.method == 'POST':
        fields = []

        autopilot = request.data.get('autopilot_active')
        if autopilot is not None:
            user.autopilot_active = bool(autopilot)
            fields.append('autopilot_active')

        mode = request.data.get('unsubscribe_mode')
        if mode is not None:
            valid = {c[0] for c in user.UNSUBSCRIBE_MODE_CHOICES}
            if mode not in valid:
                return Response({'error': f'unsubscribe_mode must be one of {sorted(valid)}.'},
                                status=status.HTTP_400_BAD_REQUEST)
            user.unsubscribe_mode = mode
            fields.append('unsubscribe_mode')

        text = request.data.get('unsubscribe_text')
        if text is not None:
            if not str(text).strip():
                return Response({'error': 'unsubscribe_text cannot be empty.'},
                                status=status.HTTP_400_BAD_REQUEST)
            user.unsubscribe_text = str(text).strip()[:200]
            fields.append('unsubscribe_text')

        if not fields:
            return Response({'error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)

        user.save(update_fields=fields)
        return Response({
            'success': True,
            'autopilot_active': user.autopilot_active,
            'unsubscribe_mode': user.unsubscribe_mode,
            'unsubscribe_text': user.unsubscribe_text,
        })

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            "message": "User created successfully",
            "full_name": user.get_full_name(),
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRequestThrottle])
def request_password_reset(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if not settings.PASSWORD_RESET_EMAIL_ENABLED:
        return Response(
            {"detail": "Password reset email is not configured yet."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    User = get_user_model()
    matching_users = User.objects.filter(
        email__iexact=serializer.validated_data['email'], is_active=True,
    )
    if matching_users.count() == 1:
        user = matching_users.first()
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?{urlencode({'uid': uid, 'token': token})}"
        from email.utils import formataddr
        sender = formataddr((settings.PASSWORD_RESET_FROM_NAME, settings.PASSWORD_RESET_SENDER_ADDRESS))
        message = (
            f"We received a request to reset the password for your Rich Lead account.\n\n"
            f"Use this secure link to choose a new password:\n{reset_url}\n\n"
            "If you did not request this, you can ignore this email. The link expires automatically."
        )
        try:
            send_mail(
                "Reset your Rich Lead password",
                message,
                sender,
                [user.email],
                fail_silently=False,
            )
        except Exception:
            # Keep the response identical for existing and unknown addresses.
            logger.exception("Password reset email delivery failed")

    return Response(
        {"detail": "If an account exists for that email, a reset link will be sent."},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetConfirmThrottle])
def confirm_password_reset(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    user = serializer.validated_data['user']
    user.set_password(serializer.validated_data['new_password'])
    user.save(update_fields=['password'])
    return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
