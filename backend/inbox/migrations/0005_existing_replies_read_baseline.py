from django.db import migrations


def mark_existing_inbound_as_read(apps, schema_editor):
    EmailMessage = apps.get_model('inbox', 'EmailMessage')
    EmailMessage.objects.filter(direction='inbound', is_read=False).update(is_read=True)


class Migration(migrations.Migration):
    dependencies = [
        ('inbox', '0004_dedupe_outbound_echoes'),
    ]

    operations = [
        migrations.RunPython(mark_existing_inbound_as_read, migrations.RunPython.noop),
    ]
