# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-08-02 21:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0004_userprofile_seat_squashed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='seat',
            field=models.CharField(blank=True, default='', help_text='Enter your seat so we can find you easily if you get stuck. (To help you, not to mock you <3)', max_length=12),
        ),
    ]
