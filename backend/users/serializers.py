import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
from rest_framework import serializers

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    email = serializers.EmailField(required=True)
    full_name = serializers.CharField(write_only=True, required=True, max_length=150)

    class Meta:
        model = User
        fields = ('full_name', 'email', 'password')

    def validate_full_name(self, value):
        normalised = " ".join(value.split())
        if not normalised:
            raise serializers.ValidationError("Enter your full name.")
        return normalised

    def validate_email(self, value):
        """Emails must be unique. AbstractUser.email is not unique by default, which
        makes password reset ambiguous and enables account-confusion attacks."""
        normalised = value.strip().lower()
        if User.objects.filter(email__iexact=normalised).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return normalised

    def create(self, validated_data):
        full_name = validated_data.pop('full_name')
        first_name, _, last_name = full_name.partition(' ')
        email = validated_data['email']
        base = slugify(full_name)[:130] or slugify(email.split('@', 1)[0])[:130] or 'user'
        username = f"{base}-{uuid.uuid4().hex[:10]}"
        while User.objects.filter(username__iexact=username).exists():
            username = f"{base}-{uuid.uuid4().hex[:10]}"

        return User.objects.create_user(
            username=username,
            first_name=first_name,
            last_name=last_name,
            email=email,
            password=validated_data['password'],
        )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=256)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode

        try:
            user_id = force_str(urlsafe_base64_decode(attrs['uid']))
            user = User.objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "This reset link is invalid or expired."})

        if not default_token_generator.check_token(user, attrs['token']):
            raise serializers.ValidationError({"token": "This reset link is invalid or expired."})

        try:
            validate_password(attrs['new_password'], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc

        attrs['user'] = user
        return attrs
