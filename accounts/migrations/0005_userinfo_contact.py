# Generated by Django 3.0.2 on 2020-10-31 18:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_auto_20190223_1016'),
    ]

    operations = [
        migrations.AddField(
            model_name='userinfo',
            name='contact',
            field=models.BooleanField(help_text="We won't spam you, only important information about our events.", null=True, verbose_name='May we contact you?'),
        ),
    ]
