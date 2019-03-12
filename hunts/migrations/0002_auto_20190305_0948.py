# Generated by Django 2.1.7 on 2019-03-05 09:48

from django.db import migrations
import enumfields.fields
import hunts.runtimes


class Migration(migrations.Migration):

    dependencies = [
        ('hunts', '0001_squashed_0017_auto_20190209_1436'),
    ]

    operations = [
        migrations.AlterField(
            model_name='answer',
            name='runtime',
            field=enumfields.fields.EnumField(default='S', enum=hunts.runtimes.Runtime, help_text='Processor to use to check whether guess is correct', max_length=1, verbose_name='Validator'),
        ),
        migrations.AlterField(
            model_name='puzzle',
            name='cb_runtime',
            field=enumfields.fields.EnumField(default='S', enum=hunts.runtimes.Runtime, help_text='Processor used to execute the callback script in response to AJAX requests', max_length=1, verbose_name='AJAX callback processor'),
        ),
        migrations.AlterField(
            model_name='puzzle',
            name='runtime',
            field=enumfields.fields.EnumField(default='S', enum=hunts.runtimes.Runtime, help_text='Renderer for generating the main puzzle page', max_length=1, verbose_name='Puzzle page renderer'),
        ),
        migrations.AlterField(
            model_name='puzzle',
            name='soln_runtime',
            field=enumfields.fields.EnumField(default='S', enum=hunts.runtimes.Runtime, help_text='Renderer for generating the question solution', max_length=1, verbose_name='Solution renderer'),
        ),
        migrations.AlterField(
            model_name='unlockanswer',
            name='runtime',
            field=enumfields.fields.EnumField(default='S', enum=hunts.runtimes.Runtime, help_text='Processor to use to check whether guess unlocks this unlock', max_length=1, verbose_name='Validator'),
        ),
    ]
