# Generated by Django 3.1.6 on 2021-04-25 16:32

from django.db import migrations, models
import django.db.models.deletion


def create_progress(apps, schema_editor):
    TeamPuzzleData = apps.get_model('hunts', 'TeamPuzzleData')
    TeamPuzzleProgress = apps.get_model('hunts', 'TeamPuzzleProgress')
    TeamUnlock = apps.get_model('hunts', 'TeamUnlock')
    Guess = apps.get_model('hunts', 'Guess')
    UnlockAnswer = apps.get_model('hunts', 'UnlockAnswer')

    for tpd in TeamPuzzleData.objects.all():
        tpp = TeamPuzzleProgress(puzzle=tpd.puzzle, team=tpd.team, start_time=tpd.start_time)
        guesses = Guess.objects.filter(
            by_team=tpd.team,
            for_puzzle=tpd.puzzle
        )
        guess = guesses.filter(
            correct_for__isnull=False,
        ).order_by(
            'given'
        ).first()
        if guess:
            tpp.solved_by = guess
        tpp.save()

        unlockanswers = UnlockAnswer.objects.filter(
            unlock__puzzle=tpd.puzzle
        )
        for guess in guesses:
            for unlockanswer in unlockanswers:
                if unlockanswer.runtime.create(unlockanswer.options).validate_guess(
                    unlockanswer.guess,
                    guess.guess,
                ):
                    TeamUnlock(
                        team_puzzle_progress=tpp, unlockanswer=unlockanswer, unlocked_by=guess
                    ).save()



class Migration(migrations.Migration):

    dependencies = [
        ('teams', '0007_auto_20210126_2357'),
        ('hunts', '0007_auto_20201117_2202'),
    ]

    operations = [
        migrations.CreateModel(
            name='TeamPuzzleProgress',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_time', models.DateTimeField(blank=True, null=True)),
                ('puzzle', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hunts.puzzle')),
                ('solved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='hunts.guess')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='teams.team')),
            ],
            options={
                'verbose_name_plural': 'Team puzzle progresses',
            },
        ),
        migrations.CreateModel(
            name='TeamUnlock',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('team_puzzle_progress', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hunts.teampuzzleprogress')),
                ('unlockanswer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hunts.unlockanswer')),
                ('unlocked_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='hunts.Guess')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='teampuzzleprogress',
            name='unlockanswers',
            field=models.ManyToManyField(through='hunts.TeamUnlock', to='hunts.UnlockAnswer'),
        ),
        migrations.AlterUniqueTogether(
            name='teampuzzleprogress',
            unique_together={('puzzle', 'team')},
        ),
        migrations.AlterUniqueTogether(
            name='teamunlock',
            unique_together={('team_puzzle_progress', 'unlockanswer', 'unlocked_by')},
        ),
        migrations.RunPython(create_progress, migrations.RunPython.noop),
    ]
