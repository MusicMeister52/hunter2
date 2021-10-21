# Generated by Django 3.2.8 on 2021-10-27 20:49
from django.core.exceptions import ValidationError
from django.db import migrations, models


def to_nullable_puzzle_start_date(apps, schema_editor):
    Puzzle = apps.get_model('hunts', 'Puzzle')
    try:
        for pz in Puzzle.objects.all():
            pz.save()
    except ValidationError as e:
        raise ValidationError('New validation rules are failing') from e

    # Before this change, start date for puzzles on linear episodes was ignored
    Puzzle.objects.filter(start_date__isnull=False, episode__parallel=False).update(start_date=None)


def to_not_nullable_puzzle_start_date(apps, schema_editor):
    Puzzle = apps.get_model('hunts', 'Puzzle')
    # Behaviour of NULL start date is to inherit episode start date: continue that behaviour
    for pz in Puzzle.objects.filter(start_date__isnull=True):
        pz.start_date=pz.episode.start_date
        pz.save()


class Migration(migrations.Migration):

    dependencies = [
        ('hunts', '0014_auto_20210924_1123'),
    ]

    operations = [
        migrations.AlterField(
            model_name='puzzle',
            name='start_date',
            field=models.DateTimeField(blank=True, help_text='Date/Time for puzzle to start. If left blank, it will start at the same time as the episode. Otherwise, this time must be after that of the episode, and must be passed for the puzzle to be available, after taking the headstart applying to the episode into account.', null=True),
        ),
        migrations.RunPython(
            code=to_nullable_puzzle_start_date,
            reverse_code=to_not_nullable_puzzle_start_date
        ),
        migrations.AlterModelOptions(
            name='puzzle',
            options={'ordering': ('episode', 'start_date', 'order')},
        ),
        migrations.AlterField(
            model_name='episode',
            name='start_date',
            field=models.DateTimeField(help_text='Before this point, the episode is invisible and puzzles are unavailable. The actual time is affected by headstarts. Puzzles may also have their own start date which must also be passed.'),
        ),
    ]
