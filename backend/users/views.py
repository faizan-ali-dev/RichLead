import logging
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils.crypto import get_random_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import AnonRateThrottle
from rest_framework.throttling import UserRateThrottle

from .serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    EmailVerificationResendSerializer,
    EmailVerificationSerializer,
    EmailChangeConfirmSerializer,
    EmailChangeRequestSerializer,
    ProfileUpdateSerializer,
    UserRegistrationSerializer,
)

logger = logging.getLogger(__name__)


class PasswordResetRequestThrottle(AnonRateThrottle):
    scope = 'password_reset'


class PasswordResetConfirmThrottle(AnonRateThrottle):
    scope = 'password_reset_confirm'


class EmailVerificationThrottle(AnonRateThrottle):
    scope = 'email_verification'


class EmailVerificationResendThrottle(AnonRateThrottle):
    scope = 'email_verification_resend'


class EmailChangeRequestThrottle(UserRateThrottle):
    scope = 'email_change_request'


class EmailChangeConfirmThrottle(UserRateThrottle):
    scope = 'email_change_confirm'


def _send_email_verification_code(user):
    code = get_random_string(6, allowed_chars='0123456789')
    now = timezone.now()
    user.email_verification_code_hash = make_password(code)
    user.email_verification_expires_at = now + timedelta(minutes=10)
    user.email_verification_sent_at = now
    user.email_verification_attempts = 0
    user.save(update_fields=(
        'email_verification_code_hash',
        'email_verification_expires_at',
        'email_verification_sent_at',
        'email_verification_attempts',
    ))
    from email.utils import formataddr
    sender = formataddr((settings.PASSWORD_RESET_FROM_NAME, settings.PASSWORD_RESET_SENDER_ADDRESS))
    send_mail(
        'Verify your RichLead email',
        f"Your RichLead verification code is {code}. It expires in 10 minutes. If you did not create this account, ignore this email.",
        sender,
        [user.email],
        fail_silently=False,
    )

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    user = request.user
    if request.method == 'GET':
        return Response({
            'autopilot_active': user.autopilot_active,
            'reachout_language': user.reachout_language,
            'reachout_language_choices': [
                {'value': value, 'label': label}
                for value, label in user.REACHOUT_LANGUAGE_CHOICES
            ],
            'full_name': user.get_full_name().strip(),
            'nickname': user.nickname,
            'email': user.email,
            'pending_email': user.pending_email,
            'unsubscribe_mode': user.unsubscribe_mode,
            'unsubscribe_text': user.unsubscribe_text,
        })
    elif request.method == 'POST':
        fields = []

        autopilot = request.data.get('autopilot_active')
        if autopilot is not None:
            user.autopilot_active = bool(autopilot)
            fields.append('autopilot_active')

        reachout_language = request.data.get('reachout_language')
        if reachout_language is not None:
            valid = {value for value, _ in user.REACHOUT_LANGUAGE_CHOICES}
            if not isinstance(reachout_language, str) or reachout_language not in valid:
                return Response(
                    {'error': f'reachout_language must be one of {sorted(valid)}.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user.reachout_language = reachout_language
            fields.append('reachout_language')

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
            'reachout_language': user.reachout_language,
            'unsubscribe_mode': user.unsubscribe_mode,
            'unsubscribe_text': user.unsubscribe_text,
        })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    serializer = ProfileUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    full_name = serializer.validated_data['full_name']
    first_name, _, last_name = full_name.partition(' ')
    user = request.user
    user.first_name = first_name
    user.last_name = last_name
    if 'nickname' in serializer.validated_data:
        user.nickname = serializer.validated_data['nickname']
    user.save(update_fields=['first_name', 'last_name', 'nickname'])
    return Response({
        'success': True,
        'full_name': user.get_full_name().strip(),
        'nickname': user.nickname,
        'email': user.email,
    })


def _email_change_sender():
    from email.utils import formataddr
    return formataddr((settings.PASSWORD_RESET_FROM_NAME, settings.PASSWORD_RESET_SENDER_ADDRESS))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([EmailChangeRequestThrottle])
def request_email_change(request):
    serializer = EmailChangeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if not settings.PASSWORD_RESET_EMAIL_ENABLED:
        return Response(
            {'detail': 'Email changes are temporarily unavailable. Please try again later.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    user = request.user
    new_email = serializer.validated_data['new_email']
    if not user.email_verified:
        return Response(
            {'detail': 'Verify your current email before changing it.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if new_email == user.email.strip().lower():
        return Response({'detail': 'This is already your account email.'}, status=status.HTTP_400_BAD_REQUEST)
    User = get_user_model()
    if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
        return Response({'detail': 'That email address is already linked to an account.'}, status=status.HTTP_400_BAD_REQUEST)

    if (
        user.pending_email.lower() == new_email
        and user.email_change_sent_at
        and timezone.now() - user.email_change_sent_at < timedelta(minutes=1)
    ):
        return Response(
            {'detail': 'A verification code was just sent. Check the new email or wait a minute before requesting another.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    code = get_random_string(6, allowed_chars='0123456789')
    now = timezone.now()
    old_email = user.email
    user.pending_email = new_email
    user.email_change_code_hash = make_password(code)
    user.email_change_expires_at = now + timedelta(minutes=10)
    user.email_change_sent_at = now
    user.email_change_attempts = 0
    user.save(update_fields=(
        'pending_email', 'email_change_code_hash', 'email_change_expires_at',
        'email_change_sent_at', 'email_change_attempts',
    ))

    try:
        send_mail(
            'Confirm your new RichLead email',
            f"Your RichLead email-change code is {code}. It expires in 10 minutes. "
            "Your current email will stay active until you enter this code in Account Profile.",
            _email_change_sender(),
            [new_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Email change verification delivery failed')
        user.pending_email = ''
        user.email_change_code_hash = ''
        user.email_change_expires_at = None
        user.email_change_sent_at = None
        user.email_change_attempts = 0
        user.save(update_fields=(
            'pending_email', 'email_change_code_hash', 'email_change_expires_at',
            'email_change_sent_at', 'email_change_attempts',
        ))
        return Response(
            {'detail': 'We could not send the verification code. Your account email has not changed.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        send_mail(
            'RichLead email change requested',
            f"A request was made to change your RichLead account email from {old_email} to {new_email}. "
            "The change will not take effect unless the code is confirmed. If you did not request this, "
            "secure your account and contact support.",
            _email_change_sender(),
            [old_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Email change security notification delivery failed')

    return Response({
        'detail': 'A verification code has been sent to the new email. Your current email remains active until verification.',
        'pending_email': new_email,
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([EmailChangeConfirmThrottle])
def confirm_email_change(request):
    serializer = EmailChangeConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    User = get_user_model()
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if (
            not user.pending_email
            or not user.email_change_code_hash
            or not user.email_change_expires_at
            or user.email_change_expires_at <= timezone.now()
            or user.email_change_attempts >= 5
        ):
            return Response(
                {'detail': 'The code is invalid or expired. Request a new code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not check_password(serializer.validated_data['code'], user.email_change_code_hash):
            user.email_change_attempts += 1
            user.save(update_fields=['email_change_attempts'])
            return Response({'detail': 'The code is invalid or expired.'}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=user.pending_email).exclude(pk=user.pk).exists():
            return Response(
                {'detail': 'That email address is already linked to an account. Request a different address.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_email = user.email
        user.email = user.pending_email
        user.email_verified = True
        user.pending_email = ''
        user.email_change_code_hash = ''
        user.email_change_expires_at = None
        user.email_change_sent_at = None
        user.email_change_attempts = 0
        user.save(update_fields=(
            'email', 'email_verified', 'pending_email', 'email_change_code_hash',
            'email_change_expires_at', 'email_change_sent_at', 'email_change_attempts',
        ))

    try:
        send_mail(
            'Your RichLead email was changed',
            f"Your RichLead account email was changed from {old_email} to {user.email}. "
            "If you did not make this change, reset your password and contact support.",
            _email_change_sender(),
            [old_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Email change completion notification delivery failed')

    return Response({
        'detail': 'Your account email has been updated and verified.',
        'email': user.email,
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AnonRateThrottle])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        if not settings.PASSWORD_RESET_EMAIL_ENABLED:
            return Response(
                {'detail': 'Email verification is temporarily unavailable. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            with transaction.atomic():
                user = serializer.save()
                _send_email_verification_code(user)
        except Exception:
            logger.exception('Signup verification email delivery failed')
            return Response(
                {'detail': 'We could not send the verification code. Please try again.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({
            'detail': 'A verification code has been sent to your email address.',
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([EmailVerificationThrottle])
def verify_email(request):
    serializer = EmailVerificationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    User = get_user_model()
    with transaction.atomic():
        matching_users = list(User.objects.select_for_update().filter(
            email__iexact=serializer.validated_data['email'], is_active=True,
        )[:2])
        if len(matching_users) != 1:
            return Response({'detail': 'The code is invalid or expired.'}, status=status.HTTP_400_BAD_REQUEST)

        user = matching_users[0]
        if user.email_verified:
            return Response({'detail': 'Email is already verified.'}, status=status.HTTP_200_OK)

        if (
            not user.email_verification_code_hash
            or not user.email_verification_expires_at
            or user.email_verification_expires_at <= timezone.now()
            or user.email_verification_attempts >= 5
        ):
            return Response({'detail': 'The code is invalid or expired. Request a new code.'}, status=status.HTTP_400_BAD_REQUEST)

        if not check_password(serializer.validated_data['code'], user.email_verification_code_hash):
            user.email_verification_attempts += 1
            user.save(update_fields=['email_verification_attempts'])
            return Response({'detail': 'The code is invalid or expired.'}, status=status.HTTP_400_BAD_REQUEST)

        user.email_verified = True
        user.email_verification_code_hash = ''
        user.email_verification_expires_at = None
        user.email_verification_sent_at = None
        user.email_verification_attempts = 0
        user.save(update_fields=(
            'email_verified',
            'email_verification_code_hash',
            'email_verification_expires_at',
            'email_verification_sent_at',
            'email_verification_attempts',
        ))

    return Response({'detail': 'Email verified. You can now sign in.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([EmailVerificationResendThrottle])
def resend_email_verification(request):
    serializer = EmailVerificationResendSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    if not settings.PASSWORD_RESET_EMAIL_ENABLED:
        return Response(
            {'detail': 'Email verification is temporarily unavailable. Please try again later.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    identifier = serializer.validated_data['identifier']
    User = get_user_model()
    users = list(User.objects.filter(is_active=True).filter(
        Q(username__iexact=identifier) | Q(email__iexact=identifier),
    )[:2])
    if len(users) == 1:
        user = users[0]
        cooldown_passed = (
            user.email_verification_sent_at is None
            or timezone.now() - user.email_verification_sent_at >= timedelta(minutes=1)
        )
        if not user.email_verified and cooldown_passed:
            try:
                _send_email_verification_code(user)
            except Exception:
                logger.exception('Verification email resend failed')

    return Response(
        {'detail': 'If the account needs verification, a new code has been sent.'},
        status=status.HTTP_200_OK,
    )


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
    update_fields = ['password']
    if not user.email_verified:
        user.email_verified = True
        user.email_verification_code_hash = ''
        user.email_verification_expires_at = None
        user.email_verification_sent_at = None
        user.email_verification_attempts = 0
        update_fields.extend((
            'email_verified',
            'email_verification_code_hash',
            'email_verification_expires_at',
            'email_verification_sent_at',
            'email_verification_attempts',
        ))
    user.save(update_fields=update_fields)
    return Response({"detail": "Password updated successfully."}, status=status.HTTP_200_OK)
