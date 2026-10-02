from django.urls import path
from . import views

urlpatterns = [
    path('notifications/', views.InboxNotificationsView.as_view(), name='inbox-notifications'),
    path('', views.InboxListView.as_view(), name='inbox-list'),
    path('sync/', views.InboxSyncView.as_view(), name='inbox-sync'),
    path('<int:lead_id>/read/', views.mark_thread_read, name='inbox-thread-read'),
]
