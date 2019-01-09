# Generated by Django 2.1.5 on 2019-01-16 09:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_userinfo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userinfo',
            name='picture',
            field=models.URLField(blank=True, help_text='Paste a URL to an image for your profile picture'),
        ),
    ]
