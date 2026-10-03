import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('admin_dashboard', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('logged_in_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='admin_login_activities', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-logged_in_at']},
        ),
        migrations.AddIndex(
            model_name='loginactivity',
            index=models.Index(fields=['user', 'logged_in_at'], name='admin_login_user_time_idx'),
        ),
        migrations.CreateModel(
            name='SocialLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('linkedin', 'LinkedIn'), ('x', 'X'), ('facebook', 'Facebook'), ('instagram', 'Instagram'), ('youtube', 'YouTube'), ('tiktok', 'TikTok'), ('threads', 'Threads'), ('github', 'GitHub'), ('reddit', 'Reddit'), ('discord', 'Discord'), ('whatsapp', 'WhatsApp'), ('other', 'Other')], max_length=16)),
                ('label', models.CharField(blank=True, help_text='Optional accessible name for this account.', max_length=48)),
                ('url', models.URLField(max_length=500)),
                ('is_active', models.BooleanField(default=True)),
                ('display_order', models.PositiveSmallIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['display_order', 'id']},
        ),
    ]
