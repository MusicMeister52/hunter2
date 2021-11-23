# Generated by Django 3.2.9 on 2021-11-16 19:26

from django.db import migrations, models
from django_tenants.utils import tenant_context


def populate_event_index(apps, schema_editor):
    Event = apps.get_model('events', 'Event')
    Configuration = apps.get_model('hunter2', 'Configuration')
    try:
        config, _ = Configuration.objects.get_or_create()
        for e in Event.objects.all():
            e.index_text = config.index_content
            e.save()
    except Configuration.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0011_auto_20210515_2122'),
        ('hunter2', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='index_text',
            field=models.TextField(blank=True, help_text='Content for the event home page'),
        ),
        migrations.RunPython(
            code=populate_event_index,
            reverse_code=migrations.RunPython.noop,
        )
    ]