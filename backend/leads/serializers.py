from rest_framework import serializers
from .models import Lead, ScoreBreakdown, IntentSignal, AIResearch

class ScoreBreakdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoreBreakdown
        fields = ['factor', 'score', 'max_score']

class IntentSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntentSignal
        fields = ['signal', 'detected_at']

class AIResearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIResearch
        fields = ['summary', 'generated_message', 'created_at']

class LeadSerializer(serializers.ModelSerializer):
    scoreBreakdown = ScoreBreakdownSerializer(source='score_breakdowns', many=True, read_only=True)
    intentSignals = serializers.SerializerMethodField()
    researchSummary = serializers.SerializerMethodField()
    message = serializers.SerializerMethodField()
    icpScore = serializers.IntegerField(source='icp_score', required=False)

    class Meta:
        model = Lead
        fields = ['id', 'name', 'company', 'niche', 'email', 'status', 'icpScore', 'scoreBreakdown', 'intentSignals', 'researchSummary', 'message']

    def get_intentSignals(self, obj):
        return [signal.signal for signal in obj.intent_signals.all()]

    def get_researchSummary(self, obj):
        if hasattr(obj, 'research'):
            return obj.research.summary
        return None
        
    def get_message(self, obj):
        if hasattr(obj, 'research'):
            return obj.research.generated_message
        return None
