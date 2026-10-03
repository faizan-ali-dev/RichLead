from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'leads', views.LeadViewSet, basename='lead')

urlpatterns = [
    path('lead-quality/', views.lead_quality_view, name='lead-quality'),
    path('', include(router.urls)),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
]
