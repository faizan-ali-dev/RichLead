from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0004_email_verification'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='reachout_language',
            field=models.CharField(
                choices=[
                    ('en', 'English'),
                    ('ur', 'Urdu (اردو)'),
                    ('ar', 'Arabic (العربية)'),
                    ('hi', 'Hindi (हिन्दी)'),
                    ('es', 'Spanish (Español)'),
                    ('fr', 'French (Français)'),
                    ('de', 'German (Deutsch)'),
                    ('pt', 'Portuguese (Português)'),
                    ('it', 'Italian (Italiano)'),
                    ('nl', 'Dutch (Nederlands)'),
                    ('tr', 'Turkish (Türkçe)'),
                    ('ja', 'Japanese (日本語)'),
                    ('zh', 'Chinese, Simplified (简体中文)'),
                ],
                default='en',
                max_length=5,
            ),
        ),
    ]
