from django.urls import path
from . import views

urlpatterns = [
    path('', views.InboxListView.as_view(), name='inbox-list'),
    path('sync/', views.InboxSyncView.as_view(), name='inbox-sync'),
]
