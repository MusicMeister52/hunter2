# -*- coding: utf-8 -*-
# Generated by Django 1.11.3 on 2017-07-21 09:36
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hunts', '0030_merge_20170721_1028'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answer',
            name='runtime',
            field=models.CharField(choices=[('I', 'IFrame Runtime'), ('L', 'Lua Runtime'), ('R', 'Regex Runtime'), ('S', 'Static Runtime')], default='S', max_length=1),
        ),
        migrations.AlterField(
            model_name='puzzle',
            name='cb_runtime',
            field=models.CharField(choices=[('I', 'IFrame Runtime'), ('L', 'Lua Runtime'), ('R', 'Regex Runtime'), ('S', 'Static Runtime')], default='S', max_length=1),
        ),
        migrations.AlterField(
            model_name='puzzle',
            name='runtime',
            field=models.CharField(choices=[('I', 'IFrame Runtime'), ('L', 'Lua Runtime'), ('R', 'Regex Runtime'), ('S', 'Static Runtime')], default='S', max_length=1),
        ),
        migrations.AlterField(
            model_name='unlockguess',
            name='runtime',
            field=models.CharField(choices=[('I', 'IFrame Runtime'), ('L', 'Lua Runtime'), ('R', 'Regex Runtime'), ('S', 'Static Runtime')], default='S', max_length=1),
        ),
    ]
