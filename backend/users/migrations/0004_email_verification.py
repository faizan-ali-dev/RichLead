from django.db import migrations, models


def mark_existing_users_verified(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.all().update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_unsubscribe_mode_user_unsubscribe_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verification_code_hash',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verification_expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verification_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='email_verification_attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(mark_existing_users_verified, migrations.RunPython.noop),
    ]
