from django.urls import path

from . import views

urlpatterns = [
    path('track/', views.track_event, name='analytics-track'),
    path('social-links/', views.public_social_links, name='public-social-links'),
    path('access/', views.admin_access, name='admin-dashboard-access'),
    path('overview/', views.admin_overview, name='admin-dashboard-overview'),
    path('users/', views.admin_users, name='admin-dashboard-users'),
    path('users/<int:user_id>/', views.admin_user_detail, name='admin-dashboard-user-detail'),
]
