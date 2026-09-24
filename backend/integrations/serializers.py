from rest_framework import serializers
from .models import APIIntegration, EmailAccount

class APIIntegrationSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=True)
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = APIIntegration
        fields = ['id', 'provider', 'api_key', 'is_active', 'created_at']

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
