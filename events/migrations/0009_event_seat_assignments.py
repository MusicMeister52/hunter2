# Generated by Django 3.0.2 on 2020-04-06 21:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0008_auto_20190409_0909'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='seat_assignments',
            field=models.BooleanField(default=True, help_text='Whether the event should request seat assignments from users'),
        ),
    ]
