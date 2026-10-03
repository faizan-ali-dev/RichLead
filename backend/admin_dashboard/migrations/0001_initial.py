import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='AnalyticsEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('page_view', 'Page view'), ('cta_click', 'Call to action click')], db_index=True, max_length=16)),
                ('path', models.CharField(db_index=True, max_length=120)),
                ('label', models.CharField(blank=True, default='', max_length=64)),
                ('session_id', models.UUIDField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['event_type', 'created_at'], name='analytics_type_created_idx'),
        ),
        migrations.AddIndex(
            model_name='analyticsevent',
            index=models.Index(fields=['path', 'created_at'], name='analytics_path_created_idx'),
        ),
    ]
