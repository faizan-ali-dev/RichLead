from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from . import oauth_views

router = DefaultRouter()
router.register(r'api-keys', views.APIIntegrationViewSet, basename='apikey')
router.register(r'email-accounts', views.EmailAccountViewSet, basename='emailaccount')
router.register(r'suppression', views.SuppressionEntryViewSet, basename='suppression')

urlpatterns = [
    path('send-email/', views.send_email_view, name='send_email'),
    path('unsubscribe/<str:token>/', views.unsubscribe_view, name='unsubscribe'),
    path('apollo-search/', views.apollo_prospect_view, name='apollo_search'),
    path('hunter-search/', views.hunter_prospect_view, name='hunter_search'),
    
    # OAuth Routes
    path('oauth/google/init/', oauth_views.google_oauth_init, name='google_oauth_init'),
    path('oauth/google/callback/', oauth_views.google_oauth_callback, name='google_oauth_callback'),
    path('oauth/microsoft/init/', oauth_views.microsoft_oauth_init, name='microsoft_oauth_init'),
    path('oauth/microsoft/callback/', oauth_views.microsoft_oauth_callback, name='microsoft_oauth_callback'),
    
    path('', include(router.urls)),
]
