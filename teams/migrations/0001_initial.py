# -*- coding: utf-8 -*-
# Generated by Django 1.11.13 on 2018-05-13 16:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('events', '0001_initial'),
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Team',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, max_length=100)),
                ('is_admin', models.BooleanField(default=False)),
                ('at_event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='teams', to='events.Event')),
                ('invites', models.ManyToManyField(blank=True, related_name='team_invites', to='accounts.UserProfile')),
                ('members', models.ManyToManyField(blank=True, related_name='teams', to='accounts.UserProfile')),
                ('requests', models.ManyToManyField(blank=True, related_name='team_requests', to='accounts.UserProfile')),
            ],
        ),
    ]
