from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('statistic', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='helpdeskcategoryafl',
            name='ticket_ids',
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name='helpdeskcategoryakr',
            name='ticket_ids',
            field=models.JSONField(default=list),
        ),
    ]