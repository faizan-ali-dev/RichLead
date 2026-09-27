from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('integrations', '0007_alter_apiintegration_unique_together_and_more')]

    operations = [
        migrations.AddField(
            model_name='oauthstate',
            name='browser_binding_hash',
            field=models.CharField(default='', max_length=64),
            preserve_default=False,
        ),
    ]
