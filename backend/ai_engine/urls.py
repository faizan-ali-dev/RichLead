from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'prompts', views.PromptTemplateViewSet, basename='prompt')

urlpatterns = [
    path('process-lead/', views.process_lead, name='process_lead'),
    path('', include(router.urls)),
]
