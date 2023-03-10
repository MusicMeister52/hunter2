# Generated by Django 3.2.9 on 2021-11-09 21:38

from django.db import connections, migrations, models
import django.db.models.deletion
from django_tenants.utils import get_tenant_database_alias


def populate_announcement_event(apps, schema_editor):
    Announcement = apps.get_model('hunts', 'Announcement')
    Event = apps.get_model('events', 'Event')
    # The tenant object on the DB connection here is a `django_tenants.postgresql_backend.base.FakeTenant` which only knows the schema name, not the ID
    event = Event.objects.get(schema_name=connections[get_tenant_database_alias()].tenant.schema_name)
    Announcement.objects.update(event=event)


class Migration(migrations.Migration):

    dependencies = [
        ('hunts', '0015_linear_episode_start_dates'),
    ]

    operations = [
        # We have to first alter the field to be nullable so that the reverse migration can populate it
        migrations.AlterField(
            model_name='announcement',
            name='event',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, related_name='announcements', to='events.Event', blank=True, null=True),
        ),
        migrations.RunPython(
            code=migrations.RunPython.noop,
            reverse_code=populate_announcement_event,
        ),
        migrations.RemoveField(
            model_name='announcement',
            name='event',
        ),
    ]
