# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-08-10 16:48
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_auto_20170804_0029'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='about_text',
            field=models.TextField(default='This page should contain information about the event', help_text='Content for the event about page'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='event',
            name='rules_text',
            field=models.TextField(default='This page should contain the event rules', help_text='Content for the event rules page'),
            preserve_default=False,
        ),
    ]
