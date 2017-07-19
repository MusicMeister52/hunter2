# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-04-25 10:29
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='teams',
        ),
        migrations.AddField(
            model_name='team',
            name='invites',
            field=models.ManyToManyField(related_name='team_invites', to='teams.UserProfile'),
        ),
        migrations.AddField(
            model_name='team',
            name='members',
            field=models.ManyToManyField(related_name='teams', to='teams.UserProfile'),
        ),
        migrations.AddField(
            model_name='team',
            name='requests',
            field=models.ManyToManyField(related_name='team_requests', to='teams.UserProfile'),
        ),
    ]
