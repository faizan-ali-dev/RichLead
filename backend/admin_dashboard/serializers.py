from rest_framework import serializers


class AnalyticsEventSerializer(serializers.Serializer):
    event_type = serializers.ChoiceField(choices=('page_view', 'cta_click'))
    path = serializers.RegexField(r'^/[A-Za-z0-9/_-]{0,119}$', max_length=120)
    session_id = serializers.UUIDField()
    label = serializers.RegexField(r'^[A-Za-z0-9_-]{1,64}$', required=False, allow_blank=True, default='')

    def validate(self, attrs):
        if attrs['event_type'] == 'page_view' and attrs.get('label'):
            raise serializers.ValidationError({'label': 'Page views cannot include a label.'})
        if attrs['event_type'] == 'cta_click' and not attrs.get('label'):
            raise serializers.ValidationError({'label': 'CTA clicks must include a short event label.'})
        return attrs


class AdminUserUpdateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=False, trim_whitespace=True)
    nickname = serializers.CharField(max_length=80, required=False, allow_blank=True, trim_whitespace=True)
    is_active = serializers.BooleanField(required=False)
    email_verified = serializers.BooleanField(required=False)

    def validate_full_name(self, value):
        normalised = ' '.join(value.split())
        if not normalised:
            raise serializers.ValidationError('Enter the user’s full name.')
        return normalised

    def validate_nickname(self, value):
        return ' '.join(value.split())
