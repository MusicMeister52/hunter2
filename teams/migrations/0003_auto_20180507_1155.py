# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-05-07 11:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        ('teams', '0002_auto_20180507_1141'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=[
            migrations.AddField(
                model_name='team',
                name='invites',
                field=models.ManyToManyField(blank=True, related_name='team_invites', to='accounts.UserProfile'),
            ),
            migrations.AddField(
                model_name='team',
                name='members',
                field=models.ManyToManyField(blank=True, related_name='teams', to='accounts.UserProfile'),
            ),
            migrations.AddField(
                model_name='team',
                name='requests',
                field=models.ManyToManyField(blank=True, related_name='team_requests', to='accounts.UserProfile'),
            ),
        ]),
    ]
