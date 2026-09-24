from rest_framework import serializers
from .models import PromptTemplate

class PromptTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PromptTemplate
        fields = ['id', 'name', 'system_prompt', 'tone_of_voice', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        return super().create(validated_data)
