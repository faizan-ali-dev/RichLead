from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import llm_views

router = DefaultRouter()
router.register(r'prompts', views.PromptTemplateViewSet, basename='prompt')

urlpatterns = [
    # LLM provider configuration
    path('llm/catalog/', llm_views.llm_catalog, name='llm_catalog'),
    path('llm/models/', llm_views.llm_models, name='llm_models'),
    path('llm/validate/', llm_views.llm_validate, name='llm_validate'),
    path('llm/connect/', llm_views.llm_connect, name='llm_connect'),
    path('llm/active/', llm_views.llm_active, name='llm_active'),
    path('llm/primary/', llm_views.llm_set_primary, name='llm_set_primary'),
    path('llm/<str:provider>/', llm_views.llm_disconnect, name='llm_disconnect'),

    # Prompt rules and spam scoring
    path('prompt-rules/', views.prompt_rules_view, name='prompt_rules'),
    path('spam-check/', views.spam_check_view, name='spam_check'),

    # Business context and follow-up cadence
    path('business-profile/', views.business_profile_view, name='business_profile'),
    path('followup-settings/', views.followup_settings_view, name='followup_settings'),

    path('draft-queue/', views.draft_queue_view, name='draft_queue'),
    path('process-lead/', views.process_lead, name='process_lead'),
    # The Leads page has always called this name; it previously 404'd.
    path('research-and-draft/', views.process_lead, name='research_and_draft'),
    path('', include(router.urls)),
]
