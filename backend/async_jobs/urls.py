from django.urls import path

from .views import job_status

urlpatterns = [
    path('<uuid:job_id>/', job_status, name='background-job-status'),
]
