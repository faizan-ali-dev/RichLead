from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    autopilot_active = models.BooleanField(default=False, help_text="If true, AI emails are sent automatically without manual review.")
