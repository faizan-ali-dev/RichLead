from django.urls import path
from . import views

urlpatterns = [
    path('settings/', views.user_settings, name='user_settings'),
    path('register/', views.register_user, name='register_user'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('verify-email/resend/', views.resend_email_verification, name='resend_email_verification'),
    path('password-reset/', views.request_password_reset, name='password_reset_request'),
    path('password-reset/confirm/', views.confirm_password_reset, name='password_reset_confirm'),
]
