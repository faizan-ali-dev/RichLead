from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0011_followupsequence'),
    ]

    operations = [
        migrations.AlterField(
            model_name='followupsequence',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('paused', 'Paused'),
                    ('completed', 'Completed'),
                    ('stopped', 'Stopped'),
                    ('failed', 'Failed'),
                ],
                default='active',
                max_length=12,
            ),
        ),
    ]
