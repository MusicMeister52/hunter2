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


import collections
import json
import re
from datetime import timedelta
from random import choice

import factory
import pytz
from faker import Faker

from accounts.factories import UserProfileFactory
from events.factories import EventFactory
from teams.factories import TeamFactory, TeamMemberFactory
from .models import AnnouncementType
from . import runtimes


class EpisodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Episode'

    class Params:
        not_started = factory.Trait(
            start_data=factory.Faker('date_time_this_month', before_now=False, after_now=True, tzinfo=pytz.utc)
        )

    name = factory.Faker('sentence')
    flavour = factory.Faker('text')
    start_date = factory.Faker('date_time_this_month', tzinfo=pytz.utc)
    event = factory.SubFactory(EventFactory)
    parallel = factory.Faker('boolean')

    @factory.post_generation
    def prequels(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of prequels were passed in, use them
            for prequel in (extracted if isinstance(extracted, collections.Iterable) else (extracted,)):
                self.prequels.add(prequel)

    @factory.post_generation
    def headstart_from(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of  puzzles were passed in, use them
            for puzzle in (extracted if isinstance(extracted, collections.Iterable) else (extracted,)):
                self.headstart_from.add(puzzle)


class PuzzleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Puzzle'

    class Params:
        not_started = factory.Trait(
            start_data=factory.Faker('date_time_this_month', before_now=False, after_now=True, tzinfo=pytz.utc)
        )

    episode = factory.SubFactory(EpisodeFactory)

    title = factory.Faker('sentence')
    flavour = factory.Faker('text')

    # TODO: Consider extending to use other runtimes as well.
    runtime = runtimes.STATIC
    content = factory.Faker('text')

    # TODO: Use other runtimes when we are testing callbacks.
    cb_runtime = runtimes.STATIC
    cb_content = ""

    # TODO: Use other runtimes when we are testing solutions.
    soln_runtime = runtimes.STATIC
    soln_content = factory.Faker('text')

    start_date = factory.Faker('date_time_this_month', tzinfo=pytz.utc)
    headstart_granted = factory.Faker('time_delta', end_datetime=timedelta(minutes=60))

    # This puzzle needs to be part of an episode & have at least one answer
    answer_set = factory.RelatedFactory('hunts.factories.AnswerFactory', 'for_puzzle')

    @factory.post_generation
    def answers(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for answer in (extracted if isinstance(extracted, collections.Iterable) else (extracted,)):
                self.answer_set.add(answer)


class PuzzleFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.PuzzleFile'
        django_get_or_create = ('puzzle', 'slug', 'url_path')

    puzzle = factory.SubFactory(PuzzleFactory)
    slug = factory.Faker('word')
    url_path = factory.Faker('file_path')  # This will have a superfluous / on the beginning but this is fine.
    file = factory.django.FileField(
        filename=factory.Faker('file_name'),
        data=factory.Faker('binary')
    )


class SolutionFileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.SolutionFile'
        django_get_or_create = ('puzzle', 'slug', 'url_path')

    puzzle = factory.SubFactory(PuzzleFactory)
    slug = factory.Faker('word')
    url_path = factory.Faker('file_path')  # This will have a superfluous / on the beginning but this is fine.
    file = factory.django.FileField(
        filename=factory.Faker('file_name'),
        data=factory.Faker('binary')
    )


class HintFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Hint'

    puzzle = factory.SubFactory(PuzzleFactory)
    text = factory.Faker('sentence')
    time = factory.Faker('time_delta', end_datetime=timedelta(minutes=60))


class UnlockFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Unlock'
        exclude = ('answer',)

    puzzle = factory.SubFactory(PuzzleFactory)
    text = factory.Faker('sentence')
    answer = factory.RelatedFactory('hunts.factories.UnlockAnswerFactory', 'unlock')


class UnlockAnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.UnlockAnswer'

    unlock = factory.SubFactory(UnlockFactory, answer=None)
    runtime = runtimes.STATIC
    guess = factory.Faker('word')


class AnswerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Answer'

    @staticmethod
    def _generate_static_answer():
        return Faker().word()

    @staticmethod
    def _generate_regex_answer():
        # TODO: Extend to abitrary regex & use exrex to solve.
        return fr'{Faker().word()}\d\d\d'

    @staticmethod
    def _generate_lua_answer():
        # TODO: Make more complicated & dynamic
        return f'return guess == "{Faker().word()}"'

    @staticmethod
    def _generate_answer(obj):
        try:
            return {
                runtimes.STATIC: lambda: AnswerFactory._generate_static_answer(),
                runtimes.REGEX: lambda: AnswerFactory._generate_regex_answer(),
                runtimes.LUA: lambda: AnswerFactory._generate_lua_answer()
            }[obj.runtime]()
        except KeyError as error:
            raise NotImplemented("Unknown runtime") from error

    for_puzzle = factory.SubFactory(PuzzleFactory, answer_set=None)
    runtime = factory.Faker('random_element', elements=(
        runtimes.STATIC, runtimes.STATIC, runtimes.STATIC, runtimes.REGEX, runtimes.LUA,
    ))
    answer = factory.LazyAttribute(lambda o: AnswerFactory._generate_answer(o))


class GuessFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Guess'
        exclude = ('event',)

    class Params:
        correct = factory.Trait(
            guess=factory.LazyAttribute(lambda o: GuessFactory._generate_correct_answer(o.for_puzzle.answer_set.get()))
        )

    @staticmethod
    def _generate_correct_static_guess(answer):
        return answer

    @staticmethod
    def _generate_correct_regex_guess(answer):
        # TODO: Extend to abitrary regex & use exrex to solve.
        match = re.fullmatch(r"(.+)\\d\\d\\d", answer)
        if match:
            return match.group(1) + str(Faker().random_number(digits=3, fix_len=True))
        else:
            raise NotImplemented("Can't parse Regex Answer, perhaps it was not generated by AnswerFactory?")

    @staticmethod
    def _generate_correct_lua_guess(answer):
        match = re.fullmatch(r"return guess == \"(.+)\"", answer)
        if match:
            return match.group(1)
        else:
            raise NotImplemented("Can't parse Lua Answer, perhaps it was not generated by AnswerFactory?")

    @staticmethod
    def _generate_correct_answer(answer):
        try:
            return {
                runtimes.STATIC: lambda: GuessFactory._generate_correct_static_guess(answer.answer),
                runtimes.REGEX: lambda: GuessFactory._generate_correct_regex_guess(answer.answer),
                runtimes.LUA: lambda: GuessFactory._generate_correct_lua_guess(answer.answer)
            }[answer.runtime]()
        except KeyError as error:
            raise NotImplemented("Unknown runtime") from error

    # A Guess can only be made by a User who is on a Team at an Event.
    # We need to ensure that there is this consistency:
    # UserProfile(by) <-> Team <-> Event <-> Episode <-> Puzzle(for_puzzle)
    for_puzzle = factory.SubFactory(PuzzleFactory)
    event = factory.LazyAttribute(lambda o: o.for_puzzle.episode.event)
    by = factory.LazyAttribute(lambda o: TeamMemberFactory(team__at_event=o.event))
    guess = factory.Faker('sentence')
    given = factory.Faker('past_datetime', start_date='-1d', tzinfo=pytz.utc)
    # by_team, correct_for and correct_current are all handled internally.


class DataFactory(factory.django.DjangoModelFactory):
    class Meta:
        abstract = True

    data = factory.LazyFunction(lambda: json.dumps(Faker().pydict(
        10,
        True,
        'str', 'str', 'str', 'str', 'float', 'int', 'int',
    )))


class TeamDataFactory(DataFactory):
    class Meta:
        model = 'hunts.TeamData'

    team = factory.SubFactory(TeamFactory)


class UserDataFactory(DataFactory):
    class Meta:
        model = 'hunts.UserData'
        django_get_or_create = ('event', 'user')

    event = factory.SubFactory(EventFactory)
    user = factory.SubFactory(UserProfileFactory)


class TeamPuzzleDataFactory(DataFactory):
    class Meta:
        model = 'hunts.TeamPuzzleData'
        django_get_or_create = ('puzzle', 'team')

    puzzle = factory.SubFactory(PuzzleFactory)
    team = factory.SubFactory(TeamFactory)
    start_time = factory.Faker('date_time_this_month', tzinfo=pytz.utc)


class UserPuzzleDataFactory(DataFactory):
    class Meta:
        model = 'hunts.UserPuzzleData'
        django_get_or_create = ('puzzle', 'user')

    puzzle = factory.SubFactory(PuzzleFactory)
    user = factory.SubFactory(UserProfileFactory)
    token = factory.Faker('uuid4')


class HeadstartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Headstart'

    episode = factory.SubFactory(EpisodeFactory)
    team = factory.SubFactory(TeamFactory)
    headstart_adjustment = factory.Faker('time_delta', end_datetime=timedelta(minutes=60))


class AnnouncementFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'hunts.Announcement'

    event = factory.SubFactory(EventFactory)
    puzzle = factory.SubFactory(PuzzleFactory)  # TODO: Generate without puzzle as well.
    title = factory.Faker('sentence')
    posted = factory.Faker('date_time_this_month', tzinfo=pytz.utc)
    message = factory.Faker('text')
    type = factory.LazyFunction(lambda: choice(list(AnnouncementType)))  # nosec random is fine for testing
