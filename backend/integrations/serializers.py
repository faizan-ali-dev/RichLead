from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import DomainNameValidator
from .models import APIIntegration, EmailAccount, SuppressionEntry
from .network import UnsafeMailServer, validate_public_mail_server
from .hunter_service import HunterAPIError, validate_hunter_api_key


class SuppressionEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SuppressionEntry
        fields = ['id', 'email', 'domain', 'reason', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate(self, attrs):
        email = (attrs.get('email') or '').strip().lower()
        domain = (attrs.get('domain') or '').strip().lower().lstrip('@').rstrip('.')
        if bool(email) == bool(domain):
            raise serializers.ValidationError("Provide either an email or a domain, not both.")
        if domain:
            try:
                DomainNameValidator(accept_idna=True)(domain)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({'domain': 'Enter a valid domain name.'}) from exc
        attrs['email'] = email
        attrs['domain'] = domain
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        if validated_data['email']:
            entry, _ = SuppressionEntry.objects.get_or_create(
                user=user,
                email=validated_data['email'],
                defaults={
                    'domain': '',
                    'reason': validated_data.get('reason', 'manual'),
                    'note': validated_data.get('note', ''),
                },
            )
        else:
            entry, _ = SuppressionEntry.objects.get_or_create(
                user=user,
                domain=validated_data['domain'],
                defaults={
                    'email': '',
                    'reason': validated_data.get('reason', 'manual'),
                    'note': validated_data.get('note', ''),
                },
            )
        return entry

class APIIntegrationSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIIntegration
        fields = ['id', 'provider', 'api_key', 'is_active', 'created_at']

    def validate(self, attrs):
        if attrs.get('provider') == 'hunter':
            try:
                validate_hunter_api_key(attrs.get('api_key', ''))
            except HunterAPIError as exc:
                raise serializers.ValidationError({'api_key': str(exc)}) from exc
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        provider = validated_data['provider']
        raw_key = validated_data.pop('api_key')
        
        # Check if already exists, update if it does
        integration, created = APIIntegration.objects.get_or_create(user=user, provider=provider)
        integration.set_api_key(raw_key)
        integration.is_active = True
        integration.save()
        return integration

class EmailAccountSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    imap_password = serializers.CharField(write_only=True, required=False)
    is_connected = serializers.BooleanField(read_only=True)

    class Meta:
        model = EmailAccount
        fields = ['id', 'email_address', 'provider', 'auth_type', 'smtp_host', 'smtp_port', 'password', 'imap_host', 'imap_port', 'imap_password', 'is_connected', 'created_at']

    def validate(self, attrs):
        if attrs.get('auth_type', 'smtp') != 'smtp':
            return attrs
        for host_field, port_field in (('smtp_host', 'smtp_port'), ('imap_host', 'imap_port')):
            host = attrs.get(host_field)
            port = attrs.get(port_field)
            if host:
                try:
                    validate_public_mail_server(host, port)
                except UnsafeMailServer as exc:
                    raise serializers.ValidationError({host_field: str(exc)}) from exc
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        raw_password = validated_data.pop('password', None)
        raw_imap_password = validated_data.pop('imap_password', None)
        
        email_account = EmailAccount(user=user, **validated_data)
        if raw_password:
            email_account.set_password(raw_password)
        if raw_imap_password:
            email_account.set_imap_password(raw_imap_password)
            
        # Ideally, test SMTP connection here before saving
        email_account.is_connected = True
        email_account.save()
        return email_account
