# Copyright (C) 2018 The Hunter2 Contributors.
#
# This file is part of Hunter2.
#
# Hunter2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any later version.
#
# Hunter2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along with Hunter2.  If not, see <http://www.gnu.org/licenses/>.


import uuid
from datetime import timedelta

from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse
from django_prometheus.models import ExportModelOperationsMixin
from enumfields import EnumField, Enum
from ordered_model.models import OrderedModel

import accounts
import events
import teams
from .runtimes import Runtime


class Episode(models.Model):
    name = models.CharField(max_length=255)
    flavour = models.TextField(blank=True)
    prequels = models.ManyToManyField(
        'self', blank=True,
        help_text='Set of episodes which must be completed before starting this one', related_name='sequels',
        symmetrical=False,
    )
    start_date = models.DateTimeField()
    event = models.ForeignKey(events.models.Event, on_delete=models.DO_NOTHING)
    parallel = models.BooleanField(default=False, help_text='Allow players to answer riddles in this episode in any order they like')
    headstart_from = models.ManyToManyField(
        "self", blank=True,
        help_text='Episodes which should grant a headstart for this episode',
        symmetrical=False,
    )
    winning = models.BooleanField(default=False, help_text='Whether this episode must be won in order to win the event')

    class Meta:
        ordering = ('start_date', )
        unique_together = (('event', 'start_date'),)

    def __str__(self):
        return f'{self.event.name} - {self.name}'

    def get_absolute_url(self):
        return reverse('event') + '#episode-{}'.format(self.get_relative_id())

    def follows(self, episode):
        """Does this episode follow the provied episode by one or more prequel relationships?"""
        if episode in self.prequels.all():
            return True
        else:
            return any([p.follows(episode) for p in self.prequels.all()])

    def get_puzzle(self, puzzle_number):
        n = int(puzzle_number)
        return self.puzzle_set.all()[n - 1:n].get()

    def next_puzzle(self, team):
        """return the relative id of the next puzzle the player should attempt, or None.

        None is returned if the puzzle is parallel and there is not exactly
        one unlocked puzzle, or if it is linear and all puzzles have been unlocked."""

        if self.parallel:
            unlocked = None
            for i, puzzle in enumerate(self.puzzle_set.all()):
                if not puzzle.answered_by(team):
                    if unlocked is None:  # If this is the first not unlocked puzzle, it might be the "next puzzle"
                        unlocked = i + 1
                    else:  # We've found a second not unlocked puzzle, we can terminate early and return None
                        return None
            return unlocked  # This is either None, if we found no unlocked puzzles, or the one puzzle we found above
        else:
            for i, puzzle in enumerate(self.puzzle_set.all()):
                if not puzzle.answered_by(team):
                    return i + 1

        return None

    def started(self, team=None):
        date = self.start_date
        if team:
            date -= self.headstart_applied(team)

        return date < timezone.now()

    def get_relative_id(self):
        episodes = self.event.episode_set.order_by('start_date')
        for index, e in enumerate(episodes):
            if e == self:
                return index + 1
        return -1

    def unlocked_by(self, team):
        result = self.event.end_date < timezone.now() or \
            all([episode.finished_by(team) for episode in self.prequels.all()])
        return result

    def finished_by(self, team):
        return all([puzzle.answered_by(team) for puzzle in self.puzzle_set.all()])

    def finished_times(self):
        """Get a list of teams who have finished this episode together with the time at which they finished."""
        if not self.puzzle_set.all():
            return []

        if self.parallel:
            # The position is determined by when the latest of a team's first successful guesses came in, over
            # all puzzles in the episode. Teams which haven't answered all questions are discarded.
            last_team_guesses = {team: None for team in teams.models.Team.objects.filter(at_event=self.event)}

            for p in self.puzzle_set.all():
                team_guesses = p.first_correct_guesses(self.event)
                for team in list(last_team_guesses.keys()):
                    if team not in team_guesses:
                        del last_team_guesses[team]
                        continue
                    if not last_team_guesses[team]:
                        last_team_guesses[team] = team_guesses[team]
                    elif team_guesses[team].given > last_team_guesses[team].given:
                        last_team_guesses[team] = team_guesses[team]

            last_team_times = ((t, last_team_guesses[t].given) for t in last_team_guesses)
            return last_team_times

        else:
            last_puzzle = self.puzzle_set.all().last()
            return last_puzzle.finished_team_times(self.event)

    def finished_positions(self):
        """Get a list of teams who have finished this episode in the order in which they finished."""
        return [team for team, time in sorted(self.finished_times(), key=lambda x: x[1])]

    def headstart_applied(self, team):
        """The headstart that the team has acquired that will be applied to this episode"""
        seconds = sum([e.headstart_granted(team).total_seconds() for e in self.headstart_from.all()])
        try:
            seconds += self.headstart_set.get(team=team).headstart_adjustment.total_seconds()
        except Headstart.DoesNotExist:
            pass
        return timedelta(seconds=seconds)

    def headstart_granted(self, team):
        """The headstart that the team has acquired by completing puzzles in this episode"""
        seconds = sum([p.headstart_granted.total_seconds() for p in self.puzzle_set.all() if p.answered_by(team)])
        return timedelta(seconds=seconds)

    def _puzzle_unlocked_by(self, puzzle, team):
        now = timezone.now()
        started_puzzles = self.puzzle_set.all()
        if self.parallel:
            started_puzzles = started_puzzles.filter(start_date__lt=now)
        if self.parallel or self.event.end_date < now:
            return puzzle in started_puzzles
        else:
            for p in started_puzzles:
                if p == puzzle:
                    return True
                if not p.answered_by(team):
                    return False

    def unlocked_puzzles(self, team):
        now = timezone.now()
        started_puzzles = self.puzzle_set.all()
        if self.parallel:
            started_puzzles = started_puzzles.filter(start_date__lt=now)
        if self.parallel or self.event.end_date < now:
            return started_puzzles
        else:
            result = []
            for p in started_puzzles:
                result.append(p)
                if not p.answered_by(team):
                    break

            return result


class Puzzle(OrderedModel):
    order_with_respect_to = 'episode'

    class Meta:
        ordering = ('episode', 'order')

    episode = models.ForeignKey(Episode, blank=True, null=True, on_delete=models.SET_NULL)
    title = models.CharField(max_length=255, unique=True)
    flavour = models.TextField(
        blank=True, verbose_name="Flavour text",
        help_text="Separate flavour text for the puzzle. Should not be required for solving the puzzle")

    runtime = EnumField(
        Runtime, max_length=1, default=Runtime.STATIC,
        verbose_name='Puzzle page renderer',
        help_text='Renderer for generating the main puzzle page',
    )
    content = models.TextField(
        verbose_name='Puzzle page content',
        help_text='Main puzzle page content, generated using the puzzle renderer',
    )
    options = JSONField(
        default=dict, blank=True,
        verbose_name='Puzzle page renderer configuration',
        help_text='Options for configuring the puzzle page renderer in JSON format. Currently no options are supported.',
    )

    cb_runtime = EnumField(
        Runtime, max_length=1, default=Runtime.STATIC,
        verbose_name='AJAX callback processor',
        help_text='Processor used to execute the callback script in response to AJAX requests'
    )
    cb_content = models.TextField(
        blank=True, default='', verbose_name='AJAX callback script',
        help_text='Script for generating AJAX responses for callbacks made by puzzle',
    )
    cb_options = JSONField(
        default=dict, blank=True,
        verbose_name='AJAX callback processor configuration',
        help_text='Options for configuring the AJAX callback processor in JSON format. Currently no options are supported.',
    )

    soln_runtime = EnumField(
        Runtime, max_length=1, default=Runtime.STATIC,
        verbose_name="Solution renderer",
        help_text="Renderer for generating the question solution"
    )
    soln_content = models.TextField(
        blank=True, default='',
        verbose_name='Solution content',
        help_text='Content to be displayed to all users on the puzzle page after the event has completed'
    )
    soln_options = JSONField(
        default=dict, blank=True,
        verbose_name='Solution renderer configuration',
        help_text='Options for configuring the solution renderer in JSON format. Currently no options are supported.',
    )

    start_date = models.DateTimeField(
        blank=True, default=timezone.now,
        help_text='Date/Time for puzzle to start. Only applies if the puzzle is part of a parallel episode.'
    )
    headstart_granted = models.DurationField(
        default=timedelta(),
        help_text='How much headstart this puzzle gives to later episodes which gain headstart from this episode'
    )

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        try:
            self.runtime.create(self.options).check_script(self.content)
            self.cb_runtime.create(self.cb_options).check_script(self.cb_content)
        except SyntaxError as e:
            raise ValidationError(e) from e

    def get_absolute_url(self):
        params = {
            'episode_number': self.episode.get_relative_id(),
            'puzzle_number': self.get_relative_id()
        }
        return reverse('puzzle', kwargs=params)

    def get_relative_id(self):
        if self.episode is None:
            raise ValueError("Puzzle %s is not on an episode and so has no relative id" % self.title)

        puzzles = self.episode.puzzle_set.all()

        for i, p in enumerate(puzzles, start=1):
            if self.pk == p.pk:
                return i

        raise RuntimeError("Could not find Puzzle pk when iterating episode's puzzle list")

    def started(self, team):
        """Determine whether this puzzle should be visible to teams yet.

        Puzzles in linear episodes are always visible if their episode has started.
        Puzzles in parallel episodes become visible at their individual start time.
        """
        return not self.episode.parallel or self.start_date < timezone.now()

    def unlocked_by(self, team):
        # Is this puzzle playable?
        return self.episode.event.end_date < timezone.now() or \
            self.episode.unlocked_by(team) and self.episode._puzzle_unlocked_by(self, team)

    def answered_by(self, team):
        """Return a list of correct guesses for this puzzle by the given team, ordered by when they were given."""
        # Select related since get_correct_for() will want it
        guesses = Guess.objects.filter(
            by__in=team.members.all(),
            for_puzzle=self,
        ).order_by(
            'given'
        ).select_related('correct_for')

        # TODO: Should return bool
        return [g for g in guesses if g.get_correct_for()]

    def first_correct_guesses(self, event):
        """Returns a dictionary of teams to guesses, where the guess is that team's earliest correct, validated guess for this puzzle"""
        # Select related to avoid a load of queries for answers and teams
        correct_guesses = Guess.objects.filter(
            for_puzzle=self,
        ).order_by(
            'given'
        ).select_related('correct_for', 'by_team')

        team_guesses = {}
        for g in correct_guesses:
            if g.get_correct_for() and g.by_team not in team_guesses:
                team_guesses[g.by_team] = g

        return team_guesses

    def finished_team_times(self, event):
        """Return an iterable of (team, time) tuples of teams who have completed this puzzle at the given event,
together with the team at which they completed the puzzle."""
        team_guesses = self.first_correct_guesses(event)

        return ((team, team_guesses[team].given) for team in team_guesses)

    def finished_teams(self, event):
        """Return a list of teams who have completed this puzzle at the given event in order of completion."""
        return [team for team, time in sorted(self.finished_team_times(event), key=lambda x: x[1])]

    def position(self, team):
        """Returns the position in which the given team finished this puzzle: 0 = first, None = not yet finished."""
        try:
            return self.finished_teams(team.at_event).index(team)
        except ValueError:
            return None


def puzzle_file_path(instance, filename):
    return 'puzzles/{0}/{1}'.format(instance.puzzle.id, filename)


def solution_file_path(instance, filename):
    return 'solutions/{0}/{1}'.format(instance.puzzle.id, filename)


class PuzzleFile(models.Model):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    slug = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='Template Slug',
        help_text="Include the URL of the file in puzzle content using $slug or ${slug}.",
    )
    url_path = models.CharField(
        max_length=50,
        verbose_name='URL Filename',
        help_text='The file path you want to appear in the URL. Can include "directories" using /',
    )
    file = models.FileField(
        upload_to=puzzle_file_path,
        help_text='The extension of the uploaded file will determine the Content-Type of the file when served',
    )

    class Meta:
        unique_together = (('puzzle', 'slug'), ('puzzle', 'url_path'))


class SolutionFile(models.Model):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    slug = models.CharField(
        max_length=50, blank=True, null=True,
        verbose_name='Template Slug',
        help_text="Include the URL of the file in puzzle content using $slug or ${slug}.",
    )
    url_path = models.CharField(
        max_length=50,
        verbose_name='URL Filename',
        help_text='The file path you want to appear in the URL. Can include "directories" using /',
    )
    file = models.FileField(
        upload_to=solution_file_path,
        help_text='The extension of the uploaded file will determine the Content-Type of the file when served',
    )

    class Meta:
        unique_together = (('puzzle', 'slug'), ('puzzle', 'url_path'))


class Clue(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    text = models.TextField(help_text="Text displayed when this clue is unlocked")

    class Meta:
        abstract = True
        unique_together = (('puzzle', 'text'), )


class Hint(Clue):
    time = models.DurationField(
        verbose_name='Delay',
        help_text='Time after anyone on the team first loads the puzzle to display this hint'
    )

    def __str__(self):
        return f'Hint unlocked after {self.time}'

    def unlocked_by(self, team, data):
        if data.tp_data.start_time:
            return data.tp_data.start_time + self.time < timezone.now()
        else:
            return False


class Unlock(Clue):
    def unlocked_by(self, team):
        guesses = Guess.objects.filter(
            by__in=team.members.all()
        ).filter(
            for_puzzle=self.puzzle
        )
        unlockanswers = self.unlockanswer_set.all()
        return [g for g in guesses if any([u.validate_guess(g) for u in unlockanswers])]

    def __str__(self):
        return f'Unlock for {self.puzzle}'


class UnlockAnswer(models.Model):
    unlock = models.ForeignKey(Unlock, editable=False, on_delete=models.CASCADE)
    runtime = EnumField(
        Runtime, max_length=1, default=Runtime.STATIC,
        verbose_name='Validator',
        help_text='Processor to use to check whether guess unlocks this unlock',
    )
    options = JSONField(
        default=dict, blank=True,
        verbose_name='Validator configuration',
        help_text='''Options for configuring the validator in JSON format using the following keys:

Static:
    'case_handling':
        'none' - do not adjust case
        'lower' - compare lower case
        'fold' - perform unicode case folding
    'strip': true/false

Regex:
    'case_sensitive': true/false''',
    )
    guess = models.TextField()

    def __setattr__(self, name, value):
        # Inspired by django-immutablemodel but this project is unmaintained and we don't need the general case
        if name == 'unlock':
            try:
                current_value = getattr(self, 'unlock_id', None)
            except UnlockAnswer.DoesNotExist:
                current_value = None
            if current_value is not None and current_value != value.id:
                raise ValueError('UnlockAnswer.unlock is immutable and cannot be changed')
        super().__setattr__(name, value)

    def __str__(self):
        if self.runtime.is_printable():
            return self.guess
        else:
            return f'[Using {self.runtime}]'

    def clean(self):
        super().clean()
        try:
            self.runtime.create(self.options).check_script(self.guess)
        except SyntaxError as e:
            raise ValidationError(e) from e

    def validate_guess(self, guess):
        return self.runtime.create(self.options).validate_guess(
            self.guess,
            guess.guess,
        )


class Answer(models.Model):
    for_puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    runtime = EnumField(
        Runtime, max_length=1, default=Runtime.STATIC,
        verbose_name='Validator',
        help_text='Processor to use to check whether guess is correct',
    )
    options = JSONField(
        default=dict, blank=True,
        verbose_name='Validator configuration',
        help_text='''Options for configuring the validator in JSON format using the following keys:

Static:
    'case_handling':
        'none' - do not adjust case
        'lower' - compare lower case
        'fold' - perform unicode case folding
    'strip': true/false

Regex:
    'case_sensitive': true/false''',
    )
    answer = models.TextField()

    def __str__(self):
        if self.runtime.is_printable():
            return self.answer
        else:
            return f'[Using {self.runtime}]'

    def clean(self):
        super().clean()
        try:
            self.runtime.create(self.options).check_script(self.answer)
        except SyntaxError as e:
            raise ValidationError(e) from e

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        guesses = Guess.objects.filter(
            Q(for_puzzle=self.for_puzzle),
            Q(correct_for__isnull=True) | Q(correct_for=self)
        )
        guesses.update(correct_current=False)

    def delete(self, *args, **kwargs):
        guesses = Guess.objects.filter(
            for_puzzle=self.for_puzzle,
            correct_for=self
        )
        guesses.update(correct_current=False)
        super().delete(*args, **kwargs)

    def validate_guess(self, guess):
        return self.runtime.create(self.options).validate_guess(
            self.answer,
            guess.guess,
        )


class Guess(ExportModelOperationsMixin('guess'), models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    for_puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    by = models.ForeignKey(accounts.models.UserProfile, on_delete=models.CASCADE)
    by_team = models.ForeignKey(teams.models.Team, on_delete=models.SET_NULL, null=True, blank=True)
    guess = models.TextField()
    given = models.DateTimeField(auto_now_add=True)
    # The following two fields cache whether the guess is correct. Do not use them directly.
    correct_for = models.ForeignKey(Answer, blank=True, null=True, on_delete=models.SET_NULL)
    correct_current = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Guesses'

    def __str__(self):
        return f'"{self.guess}" by {self.by} ({self.by_team}) @ {self.given}'

    def get_team(self):
        event = self.for_puzzle.episode.event
        return teams.models.Team.objects.filter(at_event=event, members=self.by).get()

    def get_correct_for(self):
        """Get the first answer this guess is correct for, if such exists."""
        if not self.correct_current:
            self.save()

        return self.correct_for

    def _evaluate_correctness(self, data=None, answers=None):
        """Re-evaluate self.correct_current and self.correct_for.

        Sets self.correct_current to True, and self.correct_for to the first
        answer this is correct for, if such exists. Does not save the model."""
        if data is None:
            data = PuzzleData(self.for_puzzle, self.by_team)
        if answers is None:
            answers = self.for_puzzle.answer_set.all()

        self.correct_for = None
        self.correct_current = True

        for answer in answers:
            if answer.validate_guess(self):
                self.correct_for = answer
                return

    def save(self, *args, **kwargs):
        if not self.by_team:
            self.by_team = self.get_team()
        self._evaluate_correctness()
        super().save(*args, **kwargs)

    def time_on_puzzle(self):
        data = TeamPuzzleData.objects.filter(
            puzzle=self.for_puzzle,
            team=self.by_team
        ).get()
        if not data.start_time:
            # This should never happen, but can do with sample data.
            return '0'
        time_active = self.given - data.start_time
        hours, seconds = divmod(time_active.total_seconds(), 3600)
        minutes, seconds = divmod(seconds, 60)
        return '%02d:%02d:%02d' % (hours, minutes, seconds)


class TeamData(models.Model):
    team = models.OneToOneField(teams.models.Team, on_delete=models.CASCADE)
    data = JSONField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Team data'

    def __str__(self):
        return f'Data for {self.team.name}'


class UserData(models.Model):
    event = models.ForeignKey(events.models.Event, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(accounts.models.UserProfile, on_delete=models.CASCADE)
    data = JSONField(blank=True, null=True)

    class Meta:
        unique_together = (('event', 'user'), )
        verbose_name_plural = 'User data'

    def __str__(self):
        return f'Data for {self.user.username} at {self.event}'


class TeamPuzzleData(models.Model):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    team = models.ForeignKey(teams.models.Team, on_delete=models.CASCADE)
    start_time = models.DateTimeField(blank=True, null=True)
    data = JSONField(blank=True, null=True)

    class Meta:
        unique_together = (('puzzle', 'team'), )
        verbose_name_plural = 'Team puzzle data'

    def __str__(self):
        return f'Data for {self.team.name} on {self.puzzle.title}'


class UserPuzzleData(models.Model):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    user = models.ForeignKey(accounts.models.UserProfile, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    data = JSONField(blank=True, null=True)

    class Meta:
        unique_together = (('puzzle', 'user'), )
        verbose_name_plural = 'User puzzle data'

    def __str__(self):
        return f'Data for {self.user.username} on {self.puzzle.title}'

    def team(self):
        """Helper method to fetch the team associated with this user and puzzle"""
        event = self.puzzle.episode.event
        return self.user.team_at(event)


# Convenience class for using all the above data objects together
class PuzzleData:
    from .models import TeamData, UserData, TeamPuzzleData, UserPuzzleData

    def __init__(self, puzzle, team, user=None):
        self.t_data, created = TeamData.objects.get_or_create(team=team)
        self.tp_data, created = TeamPuzzleData.objects.get_or_create(
            puzzle=puzzle, team=team
        )
        if user:
            self.u_data, created = UserData.objects.get_or_create(
                event=team.at_event, user=user
            )
            self.up_data, created = UserPuzzleData.objects.get_or_create(
                puzzle=puzzle, user=user
            )

    def save(self, *args, **kwargs):
        self.t_data.save(*args, **kwargs)
        self.tp_data.save(*args, **kwargs)
        if self.u_data:
            self.u_data.save(*args, **kwargs)
        if self.up_data:
            self.up_data.save(*args, **kwargs)


class Headstart(models.Model):
    episode = models.ForeignKey(Episode, on_delete=models.CASCADE)
    team = models.ForeignKey(teams.models.Team, on_delete=models.CASCADE)
    headstart_adjustment = models.DurationField(
        default=timedelta(),
        help_text=(
            'Time difference to apply to the headstart for the team on the specified episode. '
            'This will apply in addition to any headstart they earn through other mechanisms.'
        ),
    )

    class Meta:
        unique_together = (
            ('episode', 'team'),
        )


class AnnouncementType(Enum):
    INFO = 'I'
    SUCCESS = 'S'
    WARNING = 'W'
    ERROR = 'E'


class Announcement(models.Model):
    event = models.ForeignKey(events.models.Event, on_delete=models.DO_NOTHING, related_name='announcements')
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name='announcements', null=True, blank=True)
    title = models.CharField(max_length=255)
    posted = models.DateTimeField(auto_now_add=True)
    message = models.TextField(blank=True)
    type = EnumField(AnnouncementType, max_length=1, default=AnnouncementType.INFO)

    def __str__(self):
        return self.title
