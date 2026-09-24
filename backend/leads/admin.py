from django.contrib import admin
from .models import Lead, ScoreBreakdown, IntentSignal, AIResearch

class ScoreBreakdownInline(admin.TabularInline):
    model = ScoreBreakdown
    extra = 1

class IntentSignalInline(admin.TabularInline):
    model = IntentSignal
    extra = 1

class AIResearchInline(admin.StackedInline):
    model = AIResearch

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'email', 'icp_score', 'status')
    list_filter = ('status',)
    search_fields = ('name', 'company', 'email')
    inlines = [ScoreBreakdownInline, IntentSignalInline, AIResearchInline]
