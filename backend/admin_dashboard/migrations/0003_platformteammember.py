from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def register_existing_superusers(apps, schema_editor):
    PlatformTeamMember = apps.get_model('admin_dashboard', 'PlatformTeamMember')
    user_app, user_model = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(user_app, user_model)
    database = schema_editor.connection.alias

    for user in User.objects.using(database).filter(is_superuser=True).iterator():
        PlatformTeamMember.objects.using(database).get_or_create(
            user_id=user.pk,
            defaults={
                'access_level': 'super_admin',
                'is_active': user.is_active,
            },
        )


def unregister_migrated_superusers(apps, schema_editor):
    PlatformTeamMember = apps.get_model('admin_dashboard', 'PlatformTeamMember')
    PlatformTeamMember.objects.using(schema_editor.connection.alias).filter(
        access_level='super_admin',
        created_by__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('admin_dashboard', '0002_loginactivity_sociallink'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformTeamMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('access_level', models.CharField(choices=[('super_admin', 'Super admin'), ('read_only', 'Read-only')], default='read_only', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_platform_team_members', to=settings.AUTH_USER_MODEL)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='platform_team_membership', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'platform team member',
                'verbose_name_plural': 'platform team',
                'ordering': ('access_level', 'user__email'),
            },
        ),
        migrations.RunPython(register_existing_superusers, unregister_migrated_superusers),
    ]
