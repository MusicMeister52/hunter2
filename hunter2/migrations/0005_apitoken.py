# Generated by Django 3.1.5 on 2021-01-25 00:41

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('hunter2', '0004_merge_20210123_1913'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False)),
            ],
        ),
    ]