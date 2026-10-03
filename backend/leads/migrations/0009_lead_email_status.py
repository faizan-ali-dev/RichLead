from django.db import migrations, models


def mark_provider_verified(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')
    Lead.objects.filter(source__in=('apollo', 'hunter')).update(email_status='verified')


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0008_lead_employee_count_lead_funding_amount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='email_status',
            field=models.CharField(
                choices=[('verified', 'Provider verified'), ('not_verified', 'Not verified'), ('unknown', 'Not checked')],
                db_index=True,
                default='unknown',
                max_length=16,
            ),
        ),
        migrations.RunPython(mark_provider_verified, migrations.RunPython.noop),
    ]
