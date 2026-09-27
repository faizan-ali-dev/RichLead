"""Seed the new event timestamps from the legacy `status` field.

Pre-existing leads have no first_sent_at/replied_at, so without this the dashboard
would report every historical send as never-sent. created_at is the best available
approximation of when the outreach happened.
"""
from django.db import migrations, models


def backfill(apps, schema_editor):
    Lead = apps.get_model('leads', 'Lead')

    Lead.objects.filter(status='replied', replied_at__isnull=True).update(
        replied_at=models.F('created_at')
    )
    # 'replied' implies the lead was also sent to at some point.
    Lead.objects.filter(status__in=['reached', 'replied'], first_sent_at__isnull=True).update(
        first_sent_at=models.F('created_at')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0005_lead_first_sent_at_lead_replied_at'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
