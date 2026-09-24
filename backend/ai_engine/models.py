from django.db import models
from django.conf import settings

class PromptTemplate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='prompt_templates')
    name = models.CharField(max_length=100, default="Default Outreach")
    system_prompt = models.TextField(
        default="You are an expert sales development representative. Write a highly personalized, concise cold email based on the prospect's company and recent intent signals."
    )
    tone_of_voice = models.CharField(max_length=50, default="Professional but friendly")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} for {self.user.username}"
