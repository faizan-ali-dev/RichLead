from django.urls import path
from . import views

urlpatterns = [
    path('settings/', views.user_settings, name='user_settings'),
    path('register/', views.register_user, name='register_user'),
]
