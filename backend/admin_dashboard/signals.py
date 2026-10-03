import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db import DatabaseError
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LoginActivity, PlatformTeamMember

logger = logging.getLogger(__name__)


@receiver(user_logged_in, dispatch_uid='richlead_record_admin_login_activity')
def record_login_activity(sender, request, user, **kwargs):
    if user and user.pk and user.is_active:
        try:
            LoginActivity.objects.create(user=user)
        except DatabaseError:
            logger.exception('Could not record a successful RichLead sign-in.')


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid='richlead_register_platform_superuser')
def register_platform_superuser(sender, instance, **kwargs):
    if not instance.is_superuser:
        return
    try:
        PlatformTeamMember.objects.get_or_create(
            user=instance,
            defaults={
                'access_level': PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN,
                'is_active': instance.is_active,
            },
        )
    except DatabaseError:
        # User creation can happen before this app's first migration. The data
        # migration also enrolls any existing superusers once the table exists.
        logger.exception('Could not register a RichLead platform super admin.')
