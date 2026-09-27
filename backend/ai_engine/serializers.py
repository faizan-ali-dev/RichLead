from rest_framework import serializers
from .models import BusinessProfile, FollowUpSettings, PromptTemplate


class PromptTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptTemplate
        fields = [
            'id', 'name', 'system_prompt', 'tone_of_voice',
            'sender_role', 'value_proposition', 'proof_point',
            'call_to_action', 'avoid_topics',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        make_active = validated_data.pop('is_active', True)
        # The active-template constraint is partial-unique, so the previous
        # holder must be demoted before this row is written.
        if make_active:
            PromptTemplate.objects.filter(user=validated_data['user'], is_active=True).update(is_active=False)
        validated_data['is_active'] = make_active
        return super().create(validated_data)

    def update(self, instance, validated_data):
        make_active = validated_data.pop('is_active', None)
        if make_active:
            PromptTemplate.objects.filter(
                user=instance.user, is_active=True,
            ).exclude(pk=instance.pk).update(is_active=False)
            validated_data['is_active'] = True
        elif make_active is False:
            validated_data['is_active'] = False
        return super().update(instance, validated_data)


class BusinessProfileSerializer(serializers.ModelSerializer):
    is_complete = serializers.SerializerMethodField()

    class Meta:
        model = BusinessProfile
        fields = [
            'company_name', 'website', 'industry',
            'what_you_do', 'problem_you_solve', 'ideal_customer',
            'differentiator', 'proof_points', 'case_study', 'never_claim',
            'sender_name', 'sender_title',
            'is_complete', 'updated_at',
        ]
        read_only_fields = ['is_complete', 'updated_at']

    def get_is_complete(self, obj):
        return obj.is_complete()


class FollowUpSettingsSerializer(serializers.ModelSerializer):
    total_touches = serializers.SerializerMethodField()

    class Meta:
        model = FollowUpSettings
        fields = ['enabled', 'total_follow_ups', 'days_between', 'stop_on_reply',
                  'total_touches', 'updated_at']
        read_only_fields = ['total_touches', 'updated_at']

    def get_total_touches(self, obj):
        return obj.total_touches()

    def validate_total_follow_ups(self, value):
        if value > FollowUpSettings.MAX_FOLLOW_UPS:
            raise serializers.ValidationError(
                f'More than {FollowUpSettings.MAX_FOLLOW_UPS} follow-ups drives complaints up and '
                f'replies down. Reduce the count.'
            )
        return value

    def validate_days_between(self, value):
        if value < FollowUpSettings.MIN_DAYS_BETWEEN:
            raise serializers.ValidationError(
                f'Wait at least {FollowUpSettings.MIN_DAYS_BETWEEN} days between touches. '
                f'Faster than that reads as automated.'
            )
        return value
