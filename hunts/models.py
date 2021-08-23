# Copyright (C) 2018-2021 The Hunter2 Contributors.
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

import secrets
import uuid
from collections import defaultdict
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.urls import reverse
from django_postgresql_dag.models import node_factory, edge_factory
from django_prometheus.models import ExportModelOperationsMixin
from enumfields import EnumField, Enum
from ordered_model.models import OrderedModel
from seal.models import SealableModel
from seal.query import SealableQuerySet

import accounts
import events
import teams
from teams.models import TeamRole
from . import utils
from .runtimes import Runtime


# App label qualified lazy model name is required for the django-extensions graph_models to work
# It gets confused because the referencing field is actually in the base class in a different app
class EpisodePrequel(edge_factory('hunts.Episode', concrete=False)):
    pass


class Episode(node_factory(EpisodePrequel)):
    name = models.CharField(max_length=255)
    flavour = models.TextField(blank=True)
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

    # The following 6 @property methods are aliasing the methods provided by the DAG implementation to names which make sense for our use case

    @property
    def prequels(self):
        return self.parents

    @property
    def add_prequel(self):
        return self.add_parent

    @property
    def all_prequels(self):
        return self.ancestors

    @property
    def sequels(self):
        return self.children

    @property
    def add_sequel(self):
        return self.add_child

    @property
    def all_sequels(self):
        return self.descendants

    def get_absolute_url(self):
        return reverse('event') + '#episode-{}'.format(self.get_relative_id())

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

    def available(self, team):
        """Returns whether puzzles on the episode could be available"""
        now = timezone.now()
        if self.event.end_date < now:
            return True

        if self.start_date - self.headstart_applied(team) > now:
            return False

        # Compare number of puzzles in the prequel episodes solved by the team to the total number of such puzzles
        return TeamPuzzleProgress.objects.filter(
            puzzle__episode__in=self.prequels.all(),
            team=team,
            solved_by__isnull=False,
        ).count() == Puzzle.objects.filter(episode__in=self.prequels.all()).count()

    def started(self, team):
        date = self.start_date
        if team:
            date -= self.headstart_applied(team)

        return date < timezone.now()

    def get_relative_id(self):
        episodes = self.event.episode_set.all()
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
        """Get how much headstart the given team has acquired for the episode

        This is formed from the headstart granted from those episodes which the given one specifies
        in its `headstart_from` field, plus any adjustment added for the team.
        """
        headstart = sum(TeamPuzzleProgress.objects.filter(
            team=team, puzzle__episode__in=self.headstart_from.all()
        ).headstart_granted().values(), start=timedelta(0))
        try:
            headstart += self.headstart_set.get(team=team).headstart_adjustment
        except Headstart.DoesNotExist:
            pass
        return headstart

    def headstart_granted(self, team):
        """The headstart that the team has acquired by completing puzzles in this episode"""
        seconds = sum([
            p.headstart_granted.total_seconds()
            for p in self.puzzle_set.all()
            if p.answered_by(team)
        ])
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


URL_ID_CHARS = 'abcdefghijklmnopqrstuvwxyz01234356789'


def generate_url_id():
    id = ''.join(secrets.choice(URL_ID_CHARS) for _ in range(8))
    return id


class Puzzle(OrderedModel):
    order_with_respect_to = 'episode'

    class Meta:
        ordering = ('episode', 'order')

    url_id = models.CharField(default=generate_url_id, max_length=8, editable=False, unique=True)
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
    options = models.JSONField(
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
    cb_options = models.JSONField(
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
    soln_options = models.JSONField(
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

    @property
    def abbr(self):
        if self.episode is None:
            return str(self.id)
        return f'{self.episode.get_relative_id()}.{self.get_relative_id()}'

    def available(self, team):
        """Returns whether the puzzle is available to look at and guess on"""
        now = timezone.now()
        episode = self.episode

        if episode.event.end_date < now:
            return True

        if not episode.available(team):
            return False

        if episode.parallel:
            return self.start_date < timezone.now()

        prev_puzzles = Puzzle.objects.filter(
            episode=episode,
            order__lt=self.order
        ).count()
        prev_solved_puzzles = TeamPuzzleProgress.objects.filter(
            puzzle__episode=episode,
            team=team,
            solved_by__isnull=False,
            puzzle__order__lt=self.order
        ).count()

        return prev_puzzles == prev_solved_puzzles

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
        """Return whether the team has answered this puzzle. Always results in a query."""
        return TeamPuzzleProgress.objects.filter(
            team=team, puzzle=self, solved_by__isnull=False
        ).exists()

    def first_correct_guesses(self, event):
        """Returns a dictionary of teams to guesses, where the guess is that team's earliest correct, validated guess for this puzzle"""
        # Select related to avoid a load of queries for answers and teams
        correct_guesses = Guess.objects.filter(
            for_puzzle=self,
            by_team__role=TeamRole.PLAYER,
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


class Clue(SealableModel):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    text = models.TextField(help_text="Text displayed when this clue is unlocked")

    class Meta:
        abstract = True
        unique_together = (('puzzle', 'text'), )

    @property
    def compact_id(self):
        return utils.encode_uuid(self.id)


class Hint(Clue):
    start_after = models.ForeignKey(
        'Unlock',
        verbose_name='Start after Unlock',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text='If you select an unlock here, the time will start counting from when that is unlocked.',
    )
    time = models.DurationField(
        verbose_name='Delay',
        help_text=('Time after anyone on the team first loads the puzzle or (if set) unlocks the related '
                   'unlock to display this hint'),
        validators=(MinValueValidator(timedelta(seconds=0)),),
    )

    def __str__(self):
        return f'Hint unlocked after {self.time}'

    def unlocked_by(self, team, progress, possible_guesses=None, unlocked_unlocks=None):
        """Returns whether the hint is unlocked by the given team.

        The TeamPuzzleProgress associated with the team and puzzle must be supplied.
        The following parameters can be supplied in order to speed up any calls to `Unlock.unlocked_by`:
          - An iterable of possible guesses
          - A mapping from unlock ID to unlocked time
        """
        unlocks_at = self.unlocks_at(team, progress, possible_guesses, unlocked_unlocks)
        return unlocks_at is not None and unlocks_at < timezone.now()

    def delay_for_team(self, team, progress, possible_guesses=None, unlocked_unlocks=None):
        """Returns how long until the hint unlocks for the given team.

        Parameters as for `unlocked_by`.
        """
        unlocks_at = self.unlocks_at(team, progress, possible_guesses, unlocked_unlocks)
        return None if unlocks_at is None else unlocks_at - timezone.now()

    def unlocks_at(self, team, progress, possible_guesses=None, unlocked_unlocks=None):
        """Returns when the hint unlocks for the given team.

        Parameters as for `unlocked_by`.
        """
        if self.start_after:
            if unlocked_unlocks:
                start_time = unlocked_unlocks[self.start_after.id]
            else:
                guesses = self.start_after.unlocked_by(team, possible_guesses)
                if guesses:
                    start_time = guesses[0].given
                else:
                    return None
        elif progress.start_time:
            start_time = progress.start_time
        else:
            return None

        return start_time + self.time


class Unlock(Clue):
    def unlocked_by(self, team, guesses=None):
        """Return a list of guesses (from the supplied iterable, if given) by the given team, which unlock this Unlock"""
        if guesses is None:
            guesses = list(Guess.objects.filter(
                by__in=team.members.all()
            ).filter(
                for_puzzle=self.puzzle
            ).order_by('given'))

        unlockanswers = self.unlockanswer_set.all()
        return [g for g in guesses if any([u.validate_guess(g) for u in unlockanswers])]

    def __str__(self):
        return f'"{self.text}"'


class UnlockAnswer(SealableModel):
    unlock = models.ForeignKey(Unlock, editable=False, on_delete=models.CASCADE)
    runtime = EnumField(
        Runtime, max_length=1, default=Runtime.STATIC,
        verbose_name='Validator',
        help_text='Processor to use to check whether guess unlocks this unlock',
    )
    options = models.JSONField(
        default=dict, blank=True,
        verbose_name='Validator configuration',
        help_text='''Options for configuring the validator in JSON format using the following keys:

Static:
    'case_handling': [Default: lower]
        'none' - do not adjust case
        'lower' - compare lower case
        'fold' - perform unicode case folding
    'strip': true/false [Default: true]

Regex:
    'case_sensitive': true/false [Default: false]''',
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
    options = models.JSONField(
        default=dict, blank=True,
        verbose_name='Validator configuration',
        help_text='''Options for configuring the validator in JSON format using the following keys:

Static:
    'case_handling': [Default: lower]
        'none' - do not adjust case
        'lower' - compare lower case
        'fold' - perform unicode case folding
    'strip': true/false [Default: true]

Regex:
    'case_sensitive': true/false [Default: false]''',
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

    def validate_guess(self, guess):
        return self.runtime.create(self.options).validate_guess(
            self.answer,
            guess.guess,
        )


class GuessQuerySet(SealableQuerySet):
    def evaluate_correctness(self, answers):
        """Refresh the correctness cache on the guesses in the queryset against the supplied answers"""
        for guess in self:
            guess.correct_current = True
            guess.correct_for = None
            for answer in answers:
                if answer.validate_guess(guess):
                    guess.correct_for = answer
                    break
        self.bulk_update(self, ['correct_current', 'correct_for'])


class Relationship(models.ForeignObject):
    """Defines a relationship that can be traversed in the database and ORM,
    but which doesn't add any columns to the table
    """

    def __init__(self, model, from_fields, to_fields, **kwargs):
        super().__init__(
            model,
            on_delete=models.DO_NOTHING,
            from_fields=from_fields,
            to_fields=to_fields,
            null=True,
            blank=True,
            **kwargs,
        )

    def contribute_to_class(self, cls, name, private_only=False, **kwargs):
        # override the default to always make it private
        # this ensures that no additional columns are created
        super().contribute_to_class(cls, name, private_only=True, **kwargs)


class Guess(ExportModelOperationsMixin('guess'), SealableModel):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    for_puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    by = models.ForeignKey(accounts.models.UserProfile, on_delete=models.CASCADE)
    by_team = models.ForeignKey(teams.models.Team, on_delete=models.SET_NULL, null=True, blank=True)
    guess = models.TextField()
    given = models.DateTimeField(auto_now_add=True)
    # The following two fields cache whether the guess is correct. Do not use them directly.
    correct_for = models.ForeignKey(Answer, blank=True, null=True, on_delete=models.SET_NULL)
    correct_current = models.BooleanField(default=False)

    # Directly provide a means of accessing the unique progress object associated with this guess
    # most often we're interested in using this in the opposite direction
    progress = Relationship(
        'TeamPuzzleProgress', ('by_team', 'for_puzzle'), ('team', 'puzzle'), related_name='guesses'
    )

    objects = GuessQuerySet.as_manager()

    class Meta:
        verbose_name_plural = 'Guesses'

    def __str__(self):
        return f'"{self.guess}" by {self.by} ({self.by_team}) @ {self.given}'

    def full_clean(self, exclude=("progress",), validate_unique=True):
        if "progress" not in exclude:
            exclude = exclude + ("progress",)
        super().full_clean(exclude, validate_unique)

    @property
    def compact_id(self):
        return utils.encode_uuid(self.id)

    def get_team(self):
        event = self.for_puzzle.episode.event
        return teams.models.Team.objects.filter(at_event=event, members=self.by).get()

    def get_correct_for(self):
        """Get the first answer this guess is correct for, if such exists."""
        if not self.correct_current:
            # TODO: progress: where previously saving a guess triggers a re-evaluation,
            #  now saving an existing guess does nothing for progress. Hence this needs
            #  to be reworked when reconciling the old and new progress code.
            self.save()

        return self.correct_for

    def save(self, *args, **kwargs):
        if not self.by_team_id:
            self.by_team = self.get_team()
        # ensure PuzzleData exists
        # TODO - don't do this, and enforce use of `get_or_create` or similar
        #  elsewhere. This will be easier once `TeamPuzzleProgress` is the
        #  model we need for stats and admin views, but we'll have the same
        #  problem there, then.
        PuzzleData(self.for_puzzle, self.by_team)
        super().save(*args, **kwargs)

    def time_on_puzzle(self):
        progress = TeamPuzzleProgress.objects.filter(
            puzzle=self.for_puzzle,
            team=self.by_team
        ).get()
        if not progress.start_time:
            # This should never happen, but can do with sample progress.
            return '0'
        return self.given - progress.start_time


class TeamData(models.Model):
    team = models.OneToOneField(teams.models.Team, on_delete=models.CASCADE)
    data = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name_plural = 'Team data'

    def __str__(self):
        return f'Data for {self.team.name}'


class UserData(models.Model):
    event = models.ForeignKey(events.models.Event, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(accounts.models.UserProfile, on_delete=models.CASCADE)
    data = models.JSONField(blank=True, null=True)

    class Meta:
        unique_together = (('event', 'user'), )
        verbose_name_plural = 'User data'

    def __str__(self):
        return f'Data for {self.user.username} at {self.event}'


class TeamPuzzleData(SealableModel):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    team = models.ForeignKey(teams.models.Team, on_delete=models.CASCADE)
    data = models.JSONField(blank=True, null=True)

    class Meta:
        unique_together = (('puzzle', 'team'), )
        verbose_name_plural = 'Team puzzle data'

    def __str__(self):
        return f'Data for {self.team.name} on {self.puzzle.title}'


class TeamPuzzleProgressQuerySet(SealableQuerySet):
    def with_first_correct_guess(self):
        """Annotate the queryset with the ID of the first guess which is marked as correct

        The added field is called `first_correct_guess_id`
        This relies on `correct_for` being up to date
        """
        # NOTE: if the `correct_for` field is removed from `Guess` and added to `TeamPuzzleProgress`
        # then an analog of this is probably not necessary
        return self.annotate(
            first_correct_guess_id=models.Subquery(Guess.objects.filter(
                correct_for__isnull=False,
                for_puzzle=models.OuterRef('puzzle'),
                by_team=models.OuterRef('team')
            ).order_by('given').values('pk')[:1])
        )

    def reevaluate(self):
        """Re-evaluate these Progress objects to reflect the current correct guesses

        "current correct guesses" are those whose `correct_for` is not null.
        This method is oriented to updating *progress* only, so will not make changes
        to which `solved_by` if the puzzle was previously solved and is still solved,
        or previously was not solved and is still not solved.
        """
        qs = self.with_first_correct_guess().select_related('solved_by').seal()
        for pr in qs:
            # Only update if needed, i.e. if the solvedness of the puzzle has changed, or if
            # the guess which had previously solved the puzzle is now incorrect.
            # This means for example that if a new answer is added which makes an earlier guess
            # correct, we maintain the record of the guess which originally brought the team forward.
            if not (pr.solved_by_id and pr.solved_by.correct_for_id and pr.first_correct_guess_id):
                pr.solved_by_id = pr.first_correct_guess_id
        qs.bulk_update(qs, ['solved_by_id'])

    def headstart_granted(self):
        """Transform the queryset into a dictionary of:
        (team_id, episode_id): total headstart in seconds

        Note: not every (team, episode) combination will exist as a key.
        """

        # values(<fields>) gives us a GROUP BY on those fields.
        headstart_values = self.filter(
            solved_by__isnull=False,
            puzzle__episode__isnull=False
        ).values('team', 'puzzle__episode').annotate(
            total_headstart=Sum('puzzle__headstart_granted')
        )
        # Assemble the dictionary
        return dict(((v['team'], v['puzzle__episode']), v['total_headstart']) for v in headstart_values)


class TeamPuzzleProgress(SealableModel):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    team = models.ForeignKey(teams.models.Team, on_delete=models.CASCADE)
    start_time = models.DateTimeField(blank=True, null=True)
    solved_by = models.ForeignKey(Guess, blank=True, null=True, on_delete=models.SET_NULL, related_name="+")
    unlockanswers = models.ManyToManyField(UnlockAnswer, through='TeamUnlock')

    objects = TeamPuzzleProgressQuerySet.as_manager()

    class Meta:
        unique_together = (('puzzle', 'team'), )
        verbose_name_plural = 'Team puzzle progresses'

    @property
    def unlocks(self):
        return set(ua.unlock for ua in self.unlockanswers.all())

    def hints(self):
        """Returns a dictionary of {unlock_id: visible hint}

        a key of `None` is used for hints that aren't dependent on an unlock
        """
        hints = self.puzzle.hint_set.all()
        hint_dict = defaultdict(list)
        for hint in hints:
            if hint.unlocked_by(self.team, self, self.guesses.all()):
                hint_dict[hint.start_after_id].append(hint)

        return hint_dict

    def unlocks_to_guesses(self):
        d = defaultdict(list)
        for teamunlock in self.teamunlock_set.all():
            d[teamunlock.unlockanswer.unlock.id].append(teamunlock.unlocked_by)

        return dict(d)

    def reevaluate(self, answers, guesses):
        """Update this instance to reflect the team's progress in the supplied guesses.

        This method does not save the instance.

        Args:
            answers: all the answers for the puzzle.
            guesses: all this team's guesses for the puzzle, ordered by time given.
                if some can be determined not to be correct, they can be omitted.
        """

        self.solved_by = None

        for guess in guesses:
            for answer in answers:
                if answer.validate_guess(guess):
                    self.solved_by = guess
                    break
            if self.solved_by_id:
                break


class TeamUnlock(SealableModel):
    team_puzzle_progress = models.ForeignKey(TeamPuzzleProgress, on_delete=models.CASCADE)
    unlockanswer = models.ForeignKey(UnlockAnswer, on_delete=models.CASCADE)
    unlocked_by = models.ForeignKey(Guess, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('team_puzzle_progress', 'unlockanswer', 'unlocked_by'))


class UserPuzzleData(models.Model):
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE)
    user = models.ForeignKey(accounts.models.UserProfile, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False)
    data = models.JSONField(blank=True, null=True)

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

    def __init__(self, value):
        self.variant = {
            'I': 'info',
            'S': 'success',
            'W': 'warning',
            'E': 'danger',
        }[value]


class Announcement(models.Model):
    event = models.ForeignKey(events.models.Event, on_delete=models.DO_NOTHING, related_name='announcements')
    puzzle = models.ForeignKey(Puzzle, on_delete=models.CASCADE, related_name='announcements', null=True, blank=True)
    title = models.CharField(max_length=255)
    posted = models.DateTimeField(auto_now_add=True)
    message = models.TextField(blank=True)
    type = EnumField(AnnouncementType, max_length=1, default=AnnouncementType.INFO)

    def __str__(self):
        return self.title
