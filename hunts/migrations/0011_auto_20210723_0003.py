# Generated by Django 3.1.7 on 2021-07-23 00:03

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hunts', '0010_merge_20210706_2134'),
    ]

    operations = [
        migrations.AlterField(
            model_name='teampuzzleprogress',
            name='solved_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='hunts.guess'),
        ),
    ]
