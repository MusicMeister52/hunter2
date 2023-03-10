# Generated by Django 3.2.15 on 2022-10-02 22:18

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('hunts', '0023_auto_20220919_1847'),
    ]

    operations = [
        migrations.CreateModel(
            name='HintAcceptance',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accepted_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('hint', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hunts.hint')),
                ('team_puzzle_progress', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='hint_acceptances', to='hunts.teampuzzleprogress')),
            ],
            options={
                'unique_together': {('team_puzzle_progress', 'hint')},
            },
        ),
        migrations.AddField(
            model_name='teampuzzleprogress',
            name='accepted_hints',
            field=models.ManyToManyField(through='hunts.HintAcceptance', to='hunts.Hint'),
        ),
    ]
