# Generated by Django 3.2.9 on 2021-11-16 22:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hunts', '0016_remove_announcement_event'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='headstart',
            options={'ordering': ('episode', 'headstart_adjustment')},
        ),
    ]
