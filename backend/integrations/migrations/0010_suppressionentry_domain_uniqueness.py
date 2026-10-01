from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0009_alter_apiintegration_provider'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='suppressionentry',
            name='uniq_suppression_email_per_user',
        ),
        migrations.AddConstraint(
            model_name='suppressionentry',
            constraint=models.UniqueConstraint(
                fields=('user', 'email'),
                condition=~models.Q(email=''),
                name='uniq_suppression_email_per_user',
            ),
        ),
        migrations.AddConstraint(
            model_name='suppressionentry',
            constraint=models.UniqueConstraint(
                fields=('user', 'domain'),
                condition=~models.Q(domain=''),
                name='uniq_suppression_domain_per_user',
            ),
        ),
    ]
