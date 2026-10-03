import logging

from django.contrib.auth.signals import user_logged_in
from django.db import DatabaseError
from django.dispatch import receiver

from .models import LoginActivity

logger = logging.getLogger(__name__)


@receiver(user_logged_in, dispatch_uid='richlead_record_admin_login_activity')
def record_login_activity(sender, request, user, **kwargs):
    if user and user.pk and user.is_active:
        try:
            LoginActivity.objects.create(user=user)
        except DatabaseError:
            logger.exception('Could not record a successful RichLead sign-in.')
