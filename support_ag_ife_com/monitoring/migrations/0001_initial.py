from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Server',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Название сервера')),
                ('ip_address', models.GenericIPAddressField(unique=True, verbose_name='IP-адрес')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')),
            ],
            options={'verbose_name': 'Сервер', 'verbose_name_plural': 'Серверы', 'ordering': ('id',)},
        ),
    ]
