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


import datetime
import random
import string
import time
from os import path

import factory
import freezegun
from django.apps import apps
from django.contrib import admin
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from parameterized import parameterized
from channels.testing import WebsocketCommunicator

from accounts.factories import UserFactory, UserProfileFactory
from events.factories import EventFileFactory, AttendanceFactory
from events.models import Event
from events.test import EventAwareTestCase, EventTestCase, AsyncEventTestCase, ScopeOverrideCommunicator
from hunter2.routing import application as websocket_app
from hunter2.views import DefaultEventView
from teams.models import TeamRole
from teams.factories import TeamFactory, TeamMemberFactory
from . import utils
from .context_processors import announcements
from .factories import (
    AnnouncementFactory,
    AnswerFactory,
    EpisodeFactory,
    GuessFactory,
    HeadstartFactory,
    HintFactory,
    PuzzleFactory,
    PuzzleFileFactory,
    SolutionFileFactory,
    TeamDataFactory,
    TeamPuzzleDataFactory,
    TeamPuzzleProgressFactory,
    UnlockAnswerFactory,
    UnlockFactory,
    UserDataFactory,
    UserPuzzleDataFactory,
)
from .models import EpisodePrequel, Hint, PuzzleData, PuzzleFile, SolutionFile, TeamPuzzleData, Unlock, UnlockAnswer, UserPuzzleData, TeamPuzzleProgress, \
    TeamUnlock, Answer, \
    Guess
from .utils import encode_uuid
from .runtimes import Runtime


class FactoryTests(EventTestCase):
    # TODO: Consider reworking RUNTIME_CHOICES so this can be used.
    ANSWER_RUNTIMES = [
        ("static", Runtime.STATIC),
        ("regex", Runtime.REGEX),
        ("lua",  Runtime.LUA)
    ]

    @staticmethod
    def test_puzzle_factory_default_construction():
        PuzzleFactory.create()

    @staticmethod
    def test_puzzle_file_factory_default_construction():
        PuzzleFileFactory.create()

    @staticmethod
    def test_headstart_factory_default_construction():
        HeadstartFactory.create()

    @staticmethod
    def test_hint_factory_default_construction():
        HintFactory.create()

    @staticmethod
    def test_unlock_factory_default_construction():
        UnlockFactory.create()

    @staticmethod
    def test_unlock_answer_factory_default_construction():
        UnlockAnswerFactory.create()

    @staticmethod
    def test_answer_factory_default_construction():
        AnswerFactory.create()

    @staticmethod
    def test_guess_factory_default_construction():
        GuessFactory.create()

    @parameterized.expand(ANSWER_RUNTIMES)
    def test_guess_factory_correct_guess_generation(self, _, runtime):
        answer = AnswerFactory(runtime=runtime)
        guess = GuessFactory(for_puzzle=answer.for_puzzle, correct=True)
        self.assertTrue(answer.for_puzzle.answered_by(guess.by_team), "Puzzle answered by correct guess")

    @parameterized.expand(ANSWER_RUNTIMES)
    def test_guess_factory_incorrect_guess_generation(self, _, runtime):
        answer = AnswerFactory(runtime=runtime)
        guess = GuessFactory(for_puzzle=answer.for_puzzle, correct=False)
        self.assertFalse(answer.for_puzzle.answered_by(guess.by_team), "Puzzle not answered by incorrect guess")

    @staticmethod
    def test_team_puzzle_progress_factory_default_construction():
        TeamPuzzleProgressFactory.create()

    @staticmethod
    def test_team_data_factory_default_construction():
        TeamDataFactory.create()

    @staticmethod
    def test_user_data_factory_default_construction():
        UserDataFactory.create()

    @staticmethod
    def test_team_puzzle_data_factory_default_construction():
        TeamPuzzleDataFactory.create()

    @staticmethod
    def test_user_puzzle_data_factory_default_construction():
        UserPuzzleDataFactory.create()

    @staticmethod
    def test_episode_factory_default_construction():
        EpisodeFactory.create()

    @staticmethod
    def test_announcement_factory_default_construction():
        AnnouncementFactory.create()


class AdminRegistrationTests(TestCase):
    def test_models_registered(self):
        models = apps.get_app_config('hunts').get_models()
        # Models which don't need to be directly registered due to being managed by inlines or being an M2M through model
        inline_models = (EpisodePrequel, Hint, PuzzleFile, SolutionFile, TeamUnlock, Unlock, UnlockAnswer, )
        for model in models:
            if model not in inline_models:
                self.assertIsInstance(admin.site._registry[model], admin.ModelAdmin)


class SiteSetupTest(EventAwareTestCase):
    def test_error_on_site_not_setup(self):
        # Check there is no event setup
        self.assertEqual(0, Event.objects.count())

        request = RequestFactory().get("/")
        view = DefaultEventView()
        view.setup(request)

        with self.assertRaises(ImproperlyConfigured) as context:
            view.get_redirect_url()
        self.assertIn("README", str(context.exception))

    def test_error_on_no_event(self):
        # Check there is no event already setup
        self.assertEqual(0, Event.objects.count())

        site = Site.objects.get()
        site.domain = "hunter2.local"
        site.name = "hunter2.local"
        site.save()

        request = RequestFactory().get("/")
        view = DefaultEventView()
        view.setup(request)

        with self.assertRaises(Event.DoesNotExist) as context:
            view.get_redirect_url()
        self.assertIn("README", str(context.exception))


class ErrorTests(EventTestCase):
    def test_unauthenticated_404(self):
        url = '/does/not/exist'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class HomePageTests(EventTestCase):
    def test_load_homepage(self):
        url = reverse('index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_event_script_and_style(self):
        self.tenant.script = 'console.log("hello");'
        self.tenant.style = 'body {width: 1234px;}'
        self.tenant.save()
        url = reverse('index')
        response = self.client.get(url)
        self.assertContains(response, 'console.log("hello");')
        self.assertContains(response, 'body {width: 1234px;}')


class StaticValidationTests(EventTestCase):
    @staticmethod
    def test_static_save_answer():
        AnswerFactory(runtime=Runtime.STATIC)

    @staticmethod
    def test_static_save_unlock_answer():
        UnlockAnswerFactory(runtime=Runtime.STATIC)

    def test_static_answers(self):
        answer = AnswerFactory(runtime=Runtime.STATIC)
        guess = GuessFactory(for_puzzle=answer.for_puzzle, correct=True)
        self.assertTrue(answer.validate_guess(guess))
        guess = GuessFactory(for_puzzle=answer.for_puzzle, correct=False)
        self.assertFalse(answer.validate_guess(guess))
        guess = GuessFactory(for_puzzle=answer.for_puzzle, correct=False)
        self.assertFalse(answer.validate_guess(guess))
        guess = GuessFactory(for_puzzle=answer.for_puzzle, correct=False)
        self.assertFalse(answer.validate_guess(guess))


class RegexValidationTests(EventTestCase):
    def test_regex_save_answer(self):
        AnswerFactory(runtime=Runtime.REGEX, answer='[Rr]egex.*')
        with self.assertRaises(ValidationError):
            AnswerFactory(runtime=Runtime.REGEX, answer='[NotARegex')

    def test_regex_save_unlock_answer(self):
        UnlockAnswerFactory(runtime=Runtime.REGEX, guess='[Rr]egex.*')
        with self.assertRaises(ValidationError):
            UnlockAnswerFactory(runtime=Runtime.REGEX, guess='[NotARegex')

    def test_regex_answers(self):
        answer = AnswerFactory(runtime=Runtime.REGEX, answer='cor+ect')
        guess = GuessFactory(guess='correct', for_puzzle=answer.for_puzzle)
        self.assertTrue(answer.validate_guess(guess))
        guess = GuessFactory(guess='correctnot', for_puzzle=answer.for_puzzle)
        self.assertFalse(answer.validate_guess(guess))
        guess = GuessFactory(guess='incorrect', for_puzzle=answer.for_puzzle)
        self.assertFalse(answer.validate_guess(guess))
        guess = GuessFactory(guess='wrong', for_puzzle=answer.for_puzzle)
        self.assertFalse(answer.validate_guess(guess))


class LuaValidationTests(EventTestCase):
    def test_lua_save_answer(self):
        AnswerFactory(runtime=Runtime.LUA, answer='''return {} == nil''')
        with self.assertRaises(ValidationError):
            AnswerFactory(runtime=Runtime.LUA, answer='''@''')

    def test_lua_save_unlock_answer(self):
        UnlockAnswerFactory(runtime=Runtime.LUA, guess='''return {} == nil''')
        with self.assertRaises(ValidationError):
            UnlockAnswerFactory(runtime=Runtime.LUA, guess='''@''')

    def test_lua_answers(self):
        answer = AnswerFactory(runtime=Runtime.LUA, answer='''return guess == "correct"''')
        guess = GuessFactory(guess='correct', for_puzzle=answer.for_puzzle)
        self.assertTrue(answer.validate_guess(guess))
        guess = GuessFactory(guess='correctnot', for_puzzle=answer.for_puzzle)
        self.assertFalse(answer.validate_guess(guess))
        guess = GuessFactory(guess='incorrect', for_puzzle=answer.for_puzzle)
        self.assertFalse(answer.validate_guess(guess))
        guess = GuessFactory(guess='wrong', for_puzzle=answer.for_puzzle)
        self.assertFalse(answer.validate_guess(guess))


class AnswerSubmissionTests(EventTestCase):
    def setUp(self):
        self.puzzle = PuzzleFactory()
        self.episode = self.puzzle.episode
        self.event = self.episode.event
        self.user = TeamMemberFactory(team__at_event=self.event)
        self.url = reverse('answer', kwargs={
            'episode_number': self.episode.get_relative_id(),
            'puzzle_number': self.puzzle.get_relative_id()
        },)
        self.client.force_login(self.user.user)

    def test_answer_correct(self):
        response = self.client.post(self.url, {
            'last_updated': '0',
            'answer': GuessFactory.build(for_puzzle=self.puzzle, correct=True).guess
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['correct'], 'true')

    def test_no_answer_given(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'no answer given')
        response = self.client.post(self.url, {
            'last_updated': '0',
            'answer': ''
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'no answer given')

    def test_answer_long(self):
        response = self.client.post(self.url, {
            'last_updated': '0',
            'answer': ''.join(random.choice(string.ascii_letters) for _ in range(512)),
        })
        self.assertEqual(response.status_code, 200)

    def test_answer_too_long(self):
        response = self.client.post(self.url, {
            'last_updated': '0',
            'answer': ''.join(random.choice(string.ascii_letters) for _ in range(513)),
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'answer too long')

    def test_answer_cooldown(self):
        with freezegun.freeze_time() as frozen_datetime:
            response = self.client.post(self.url, {
                'last_updated': '0',
                'answer': GuessFactory.build(for_puzzle=self.puzzle, correct=False).guess
            })
            self.assertEqual(response.status_code, 200)
            response = self.client.post(self.url, {
                'last_updated': '0',
                'answer': GuessFactory.build(for_puzzle=self.puzzle, correct=False).guess
            })
            self.assertEqual(response.status_code, 429)
            self.assertTrue(b'error' in response.content)
            frozen_datetime.tick(delta=datetime.timedelta(seconds=5))
            response = self.client.post(self.url, {
                'last_updated': '0',
                'answer': GuessFactory.build(for_puzzle=self.puzzle, correct=False).guess
            })
            self.assertEqual(response.status_code, 200)

    def test_answer_after_end(self):
        self.client.force_login(self.user.user)
        with freezegun.freeze_time() as frozen_datetime:
            self.event.end_date = timezone.now() + datetime.timedelta(seconds=5)
            self.event.save()
            response = self.client.post(self.url, {
                'last_updated': '0',
                'answer': GuessFactory.build(for_puzzle=self.puzzle, correct=False).guess
            })
            self.assertEqual(response.status_code, 200)
            frozen_datetime.tick(delta=datetime.timedelta(seconds=10))
            response = self.client.post(self.url, {
                'last_updated': '0',
                'answer': GuessFactory.build(for_puzzle=self.puzzle, correct=False).guess
            })
            self.assertEqual(response.status_code, 400)


class PuzzleStartTimeTests(EventTestCase):
    def test_start_times(self):
        self.puzzle = PuzzleFactory()
        self.episode = self.puzzle.episode
        self.event = self.episode.event
        self.user = TeamMemberFactory(team__at_event=self.event)

        self.client.force_login(self.user.user)

        response = self.client.get(self.puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200, msg='Puzzle is accessible on absolute url')

        first_time = TeamPuzzleProgress.objects.get().start_time
        self.assertIsNot(first_time, None, msg='Start time is set on first access to a puzzle')

        response = self.client.get(self.puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200, msg='Puzzle is accessible on absolute url')

        second_time = TeamPuzzleProgress.objects.get().start_time
        self.assertEqual(first_time, second_time, msg='Start time does not alter on subsequent access')


class AdminCreatePageLoadTests(EventTestCase):
    def setUp(self):
        self.user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN, user__is_staff=True)
        self.client.force_login(self.user.user)

    def test_load_announcement_add_page(self):
        response = self.client.get(reverse('admin:hunts_announcement_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_answer_add_page(self):
        response = self.client.get(reverse('admin:hunts_answer_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_episode_add_page(self):
        response = self.client.get(reverse('admin:hunts_episode_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_guess_add_page(self):
        response = self.client.get(reverse('admin:hunts_unlock_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_headstart_add_page(self):
        response = self.client.get(reverse('admin:hunts_headstart_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_puzzle_add_page(self):
        response = self.client.get(reverse('admin:hunts_puzzle_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_teamdata_add_page(self):
        response = self.client.get(reverse('admin:hunts_teamdata_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_teampuzzledata_add_page(self):
        response = self.client.get(reverse('admin:hunts_teampuzzledata_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_unlock_add_page(self):
        response = self.client.get(reverse('admin:hunts_unlock_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_userdata_add_page(self):
        response = self.client.get(reverse('admin:hunts_userdata_add'))
        self.assertEqual(response.status_code, 200)

    def test_load_userpuzzledata_add_page(self):
        response = self.client.get(reverse('admin:hunts_userpuzzledata_add'))
        self.assertEqual(response.status_code, 200)


class AdminPuzzleFormPopupTests(EventTestCase):
    def setUp(self):
        self.user = TeamMemberFactory(user__is_staff=True, team__at_event=self.tenant, team__role=TeamRole.ADMIN)
        self.client.force_login(self.user.user)
        self.puzzle = PuzzleFactory(episode__event=self.tenant)

    def test_admin_load_answer_form(self):
        AnswerFactory(for_puzzle=self.puzzle)
        response = self.client.get(reverse('admin:hunts_puzzle_change_answers', kwargs={
            'puzzle_id': self.puzzle.id,
        }))
        self.assertEqual(response.status_code, 200)

    def test_admin_load_hint_form(self):
        HintFactory(puzzle=self.puzzle)
        response = self.client.get(reverse('admin:hunts_puzzle_change_hints', kwargs={
            'puzzle_id': self.puzzle.id,
        }))
        self.assertEqual(response.status_code, 200)

    def test_admin_load_unlock_form(self):
        UnlockFactory(puzzle=self.puzzle)
        response = self.client.get(reverse('admin:hunts_puzzle_change_unlocks', kwargs={
            'puzzle_id': self.puzzle.id,
        }))
        self.assertEqual(response.status_code, 200)


class AdminPuzzleAccessTests(EventTestCase):
    def setUp(self):
        self.user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN)
        self.client.force_login(self.user.user)

    def test_admin_overrides_episode_start_time(self):
        now = timezone.now()  # We need the non-naive version of the frozen time for object creation
        with freezegun.freeze_time(now):
            start_date = now + datetime.timedelta(seconds=5)
            episode = EpisodeFactory(event=self.tenant, parallel=False, start_date=start_date)
            puzzle = PuzzleFactory.create(episode=episode, start_date=start_date)

            resp = self.client.get(reverse('puzzle', kwargs={
                'episode_number': episode.get_relative_id(),
                'puzzle_number': puzzle.get_relative_id(),
            }))
            self.assertEqual(resp.status_code, 200)

    def test_admin_overrides_puzzle_start_time(self):
        now = timezone.now()  # We need the non-naive version of the frozen time for object creation
        with freezegun.freeze_time(now):
            episode_start_date = now - datetime.timedelta(seconds=5)
            puzzle_start_date = now + datetime.timedelta(seconds=5)
            episode = EpisodeFactory(event=self.tenant, parallel=False, start_date=episode_start_date)
            puzzle = PuzzleFactory.create(episode=episode, start_date=puzzle_start_date)

            resp = self.client.get(reverse('puzzle', kwargs={
                'episode_number': episode.get_relative_id(),
                'puzzle_number': puzzle.get_relative_id(),
            }))
            self.assertEqual(resp.status_code, 200)


class PuzzleAccessTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory(event=self.tenant, parallel=False)
        self.puzzles = PuzzleFactory.create_batch(3, episode=self.episode)
        self.user = TeamMemberFactory(team__at_event=self.tenant)

    def test_puzzle_view_authorisation(self):
        self.client.force_login(self.user.user)

        def _check_load_callback_answer(puzzle, expected_response):
            kwargs = {
                'episode_number': self.episode.get_relative_id(),
                'puzzle_number': puzzle.get_relative_id(),
            }

            # Load
            resp = self.client.get(reverse('puzzle', kwargs=kwargs))
            self.assertEqual(resp.status_code, expected_response)

            # Callback
            resp = self.client.post(
                reverse('callback', kwargs=kwargs),
                content_type='application/json',
                HTTP_ACCEPT='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(resp.status_code, expected_response)

            # Answer
            resp = self.client.post(
                reverse('answer', kwargs=kwargs),
                {'answer': 'NOT_CORRECT'},  # Deliberately incorrect answer
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(resp.status_code, expected_response)

            # Solution
            resp = self.client.get(
                reverse('solution_content', kwargs=kwargs),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            # Solution should always fail with 403 except for the ended case which is separate below
            self.assertEqual(resp.status_code, 403)

        # This test submits two answers on the same puzzle so we have to jump forward 5 seconds
        with freezegun.freeze_time() as frozen_datetime:
            # Can load, callback and answer the first puzzle
            _check_load_callback_answer(self.puzzles[0], 200)

            # Answer the puzzle correctly, wait, then try again. This should fail because it's already done.
            GuessFactory(
                by=self.user,
                for_puzzle=self.puzzles[0],
                correct=True
            )
            frozen_datetime.tick(delta=datetime.timedelta(seconds=5))
            # We should be able to load the puzzle but not answer it

            # Load
            kwargs = {
                'episode_number': self.episode.get_relative_id(),
                'puzzle_number': self.puzzles[0].get_relative_id(),
            }
            resp = self.client.get(reverse('puzzle', kwargs=kwargs))
            self.assertEqual(resp.status_code, 200)

            # Callback
            resp = self.client.post(
                reverse('callback', kwargs=kwargs),
                content_type='application/json',
                HTTP_ACCEPT='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(resp.status_code, 200)

            # Answer
            resp = self.client.post(
                reverse('answer', kwargs=kwargs),
                {'answer': 'NOT_CORRECT'},  # Deliberately incorrect answer
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(resp.status_code, 422)

            # Solution
            resp = self.client.get(
                reverse('solution_content', kwargs=kwargs),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(resp.status_code, 403)

            _check_load_callback_answer(self.puzzles[1], 200)
            # Can't load, callback or answer the third puzzle
            _check_load_callback_answer(self.puzzles[2], 403)

            # Can load third puzzle, but not callback or answer after event ends
            old_time = frozen_datetime()
            frozen_datetime.move_to(self.tenant.end_date + datetime.timedelta(seconds=1))

            # Load
            kwargs = {
                'episode_number': self.episode.get_relative_id(),
                'puzzle_number': self.puzzles[2].get_relative_id(),
            }
            resp = self.client.get(reverse('puzzle', kwargs=kwargs))
            self.assertEqual(resp.status_code, 200)

            # Callback
            resp = self.client.post(
                reverse('callback', kwargs=kwargs),
                content_type='application/json',
                HTTP_ACCEPT='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(resp.status_code, 400)

            # Answer
            resp = self.client.post(
                reverse('answer', kwargs=kwargs),
                {'answer': 'NOT_CORRECT'},  # Deliberately incorrect answer
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(resp.status_code, 400)

            # Solution
            resp = self.client.get(
                reverse('solution_content', kwargs=kwargs),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(resp.status_code, 200)

            # Revert to current time
            frozen_datetime.move_to(old_time)

            # Answer the second puzzle after a delay of 5 seconds
            frozen_datetime.tick(delta=datetime.timedelta(seconds=5))
            response = self.client.post(
                reverse('answer', kwargs={
                    'episode_number': self.episode.get_relative_id(),
                    'puzzle_number': self.puzzles[1].get_relative_id()}
                ), {
                    'answer': GuessFactory.build(for_puzzle=self.puzzles[1], correct=True).guess
                },
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(response.status_code, 200)
            # Can now load, callback and answer the third puzzle
            _check_load_callback_answer(self.puzzles[2], 200)


class EpisodeBehaviourTests(EventTestCase):
    def test_linear_episodes_are_linear(self):
        linear_episode = EpisodeFactory(parallel=False)
        PuzzleFactory.create_batch(10, episode=linear_episode)
        user = UserProfileFactory()
        team = TeamFactory(at_event=linear_episode.event, members=user)

        # TODO: Scramble puzzle order before starting (so they are not in the order they were created).

        # Check we can start and that it is a linear episode.
        self.assertTrue(linear_episode.available(team), msg='Episode is unlocked by team')
        self.assertFalse(linear_episode.parallel, msg='Episode is not set as parallel')

        for i in range(1, linear_episode.puzzle_set.count() + 1):
            # Test we have unlocked the question, but not answered it yet.
            self.assertTrue(linear_episode.get_puzzle(i).available(team), msg=f'Puzzle[{i}] is locked')
            self.assertFalse(linear_episode.get_puzzle(i).answered_by(team), msg=f'Puzzle[{i}] is answered')

            # Test that we have not unlocked the next puzzle before answering.
            if i < linear_episode.puzzle_set.count():
                self.assertFalse(linear_episode.get_puzzle(i + 1).available(team), msg=f'Puzzle[{i + 1}] is not unlocked until previous puzzle answered')

            # Answer the question and assert that it's now answered.
            GuessFactory.create(for_puzzle=linear_episode.get_puzzle(i), by=user, correct=True)
            self.assertTrue(linear_episode.get_puzzle(i).answered_by(team), msg=f'Correct guess has answered puzzle[{i}]')

    def test_can_see_all_parallel_puzzles(self):
        parallel_episode = EpisodeFactory(parallel=True)
        PuzzleFactory.create_batch(5, episode=parallel_episode)
        team = TeamFactory(at_event=parallel_episode.event)

        # Check we can start and that it is a parallel episode.
        self.assertTrue(parallel_episode.available(team))
        self.assertTrue(parallel_episode.parallel)

        # Ensure all puzzles in a parallel episode are unlocked.
        for puzzle in parallel_episode.puzzle_set.all():
            self.assertTrue(puzzle.available(team), msg='Puzzle unavailable in parallel episode')

    def test_unlocked_puzzle_solved_flag(self):
        episode = EpisodeFactory(parallel=False)
        puzzles = PuzzleFactory.create_batch(5, episode=episode)
        user1 = TeamMemberFactory()
        team1 = user1.team_at(episode.event)
        user2 = TeamMemberFactory()
        team2 = user2.team_at(episode.event)
        user3 = TeamMemberFactory()
        team3 = user3.team_at(episode.event)

        # Team one has solved the first two puzzles
        for puzzle in puzzles[:2]:
            GuessFactory(by=user1, by_team=team1, for_puzzle=puzzle, correct=True)
        # ...and made some guesses on third
        GuessFactory.create_batch(5, by=user1, by_team=team1, for_puzzle=episode.puzzle_set.all()[2], correct=False)
        # Team two has solved the first three puzzles
        for puzzle in puzzles[:3]:
            GuessFactory(by=user2, by_team=team2, for_puzzle=puzzle, correct=True)
        # Team three has solved all the puzzles
        for puzzle in puzzles:
            GuessFactory(by=user3, by_team=team3, for_puzzle=puzzle, correct=True)

        url = reverse('episode_content', kwargs={'episode_number': episode.get_relative_id()})
        self.client.force_login(user1.user)
        unlocked1 = self.client.get(url).context['puzzles']
        self.assertEqual(3, len(unlocked1))
        for puzzle in unlocked1[:2]:
            self.assertTrue(puzzle.solved)
        self.assertFalse(unlocked1[2].solved)

        self.client.force_login(user2.user)
        unlocked2 = self.client.get(url).context['puzzles']
        self.assertEqual(4, len(unlocked2))
        for puzzle in unlocked2[:3]:
            self.assertTrue(puzzle.solved)
        self.assertFalse(unlocked2[3].solved)

        self.client.force_login(user3.user)
        unlocked3 = self.client.get(url).context['puzzles']
        self.assertEqual(5, len(unlocked3))
        for puzzle in unlocked3:
            self.assertTrue(puzzle.solved)

    def test_can_see_all_puzzles_after_event_end(self):
        linear_episode = EpisodeFactory(parallel=False)
        num_puzzles = 10
        PuzzleFactory.create_batch(num_puzzles, episode=linear_episode)
        user = TeamMemberFactory(team__at_event=linear_episode.event)
        self.client.force_login(user.user)
        url = reverse('episode_content', kwargs={'episode_number': linear_episode.get_relative_id()})

        with freezegun.freeze_time() as frozen_datetime:
            linear_episode.event.end_date = timezone.now()
            linear_episode.event.save()
            frozen_datetime.move_to(linear_episode.puzzle_set.last().start_date)
            team_puzzles = self.client.get(url).context['puzzles']
            self.assertEqual(len(team_puzzles), 1, msg='Before the event ends, only the first puzzle should be available')
            frozen_datetime.move_to(linear_episode.event.end_date + datetime.timedelta(seconds=1))
            team_puzzles = self.client.get(url).context['puzzles']
            self.assertEqual(len(team_puzzles), num_puzzles, msg='After the event ends, all of the puzzles should be available')

    def test_puzzle_start_dates(self):
        with freezegun.freeze_time():
            tz_time = timezone.now()
            user = TeamMemberFactory()
            self.client.force_login(user.user)

            started_parallel_episode = EpisodeFactory(start_date=tz_time - datetime.timedelta(minutes=1), parallel=True)

            started_parallel_episode_started_puzzle = PuzzleFactory(
                episode=started_parallel_episode,
                start_date=tz_time - datetime.timedelta(minutes=1)
            )
            response = self.client.get(started_parallel_episode_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            started_parallel_episode_not_started_puzzle = PuzzleFactory(
                episode=started_parallel_episode,
                start_date=tz_time + datetime.timedelta(minutes=1)
            )
            response = self.client.get(started_parallel_episode_not_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 403)
            HeadstartFactory(
                episode=started_parallel_episode,
                team=user.team_at(self.tenant),
                headstart_adjustment=datetime.timedelta(minutes=2)
            )
            response = self.client.get(started_parallel_episode_not_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 200)

            not_started_parallel_episode = EpisodeFactory(start_date=tz_time + datetime.timedelta(minutes=1), parallel=True)

            not_started_parallel_episode_not_started_puzzle = PuzzleFactory(
                episode=not_started_parallel_episode,
                start_date=tz_time + datetime.timedelta(minutes=1)
            )
            response = self.client.get(not_started_parallel_episode_not_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 302)

            started_linear_episode = EpisodeFactory(start_date=tz_time - datetime.timedelta(minutes=2), parallel=False)

            started_linear_episode_started_puzzle = PuzzleFactory(
                episode=started_linear_episode,
                start_date=tz_time - datetime.timedelta(minutes=1)
            )
            response = self.client.get(started_linear_episode_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            GuessFactory(by=user, for_puzzle=started_linear_episode_started_puzzle, correct=True)  # Create guess to progress
            started_linear_episode_not_started_puzzle = PuzzleFactory(
                episode=started_linear_episode,
                start_date=tz_time + datetime.timedelta(minutes=1)
            )
            response = self.client.get(started_linear_episode_not_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 403)
            HeadstartFactory(
                episode=started_linear_episode,
                team=user.team_at(self.tenant),
                headstart_adjustment=datetime.timedelta(minutes=2)
            )
            response = self.client.get(started_linear_episode_not_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 200)

    def test_puzzle_start_time_validation(self):
        event_end = self.tenant.end_date
        episode = EpisodeFactory()
        episode_start = episode.start_date

        with self.assertRaises(ValidationError):
            PuzzleFactory(
                episode=episode,
                start_date=episode_start - datetime.timedelta(minutes=1)
            )

        with self.assertRaises(ValidationError):
            PuzzleFactory(
                episode=episode,
                start_date=event_end + datetime.timedelta(minutes=1)
            )

        PuzzleFactory(episode=episode, start_date=episode_start + datetime.timedelta(seconds=1))

        with self.assertRaises(ValidationError):
            episode.start_date = episode.start_date + datetime.timedelta(minutes=1)
            episode.save()

        PuzzleFactory(episode=episode, start_date=event_end - datetime.timedelta(seconds=1))

        with self.assertRaises(ValidationError):
            self.tenant.end_date = self.tenant.end_date - datetime.timedelta(minutes=1)
            self.tenant.save()

    def test_headstarts(self):
        # TODO: Replace with episode sequence factory?
        episode1 = EpisodeFactory()
        episode2 = EpisodeFactory(event=episode1.event, headstart_from=episode1)
        PuzzleFactory.create_batch(10, episode=episode1)
        user = UserProfileFactory()
        team = TeamFactory(at_event=episode1.event, members=user)

        def headstart_from(episode, team):
            return TeamPuzzleProgress.objects.filter(
                team=team, puzzle__episode=episode
            ).headstart_granted().get((team.id, episode.id), datetime.timedelta(0))

        # Check that the headstart granted is the sum of the puzzle headstarts
        headstart = datetime.timedelta()
        self.assertEqual(episode1.headstart_granted(team), datetime.timedelta(minutes=0), "No headstart when puzzles unanswered")
        self.assertEqual(
            headstart_from(episode1, team),
            datetime.timedelta(0),
            "No headstart when puzzles unanswered"
        )

        for i in range(1, episode1.puzzle_set.count() + 1):
            # Start answering puzzles
            GuessFactory.create(for_puzzle=episode1.get_puzzle(i), by=user, correct=True)
            self.assertTrue(episode1.get_puzzle(i).answered_by(team), msg=f'Correct guess has answered puzzle[{i}]')

            # Check headstart summing logic.
            headstart += episode1.get_puzzle(i).headstart_granted
            self.assertEqual(episode1.headstart_granted(team), headstart, "Episode headstart is sum of answered puzzle headstarts")
            self.assertEqual(
                headstart_from(episode1, team),
                headstart,
                "Episode headstart is sum of answered puzzle headstarts"
            )

        # All of these headstarts should be applied to the second episode.
        self.assertEqual(episode2.headstart_applied(team), headstart)

        # Test that headstart does not apply in the wrong direction
        self.assertEqual(episode1.headstart_applied(team), datetime.timedelta(minutes=0))

    def test_headstart_adjustment(self):
        headstart = HeadstartFactory()

        episode = headstart.episode
        team = headstart.team

        self.assertEqual(episode.headstart_applied(team), headstart.headstart_adjustment)

    def test_headstart_adjustment_with_episode_headstart(self):
        episode1 = EpisodeFactory()
        episode2 = EpisodeFactory(event=episode1.event, headstart_from=episode1)
        puzzle = PuzzleFactory(episode=episode1)
        user = UserProfileFactory()
        team = TeamFactory(at_event=episode1.event, members=user)
        GuessFactory(for_puzzle=puzzle, by=user, correct=True)
        headstart = HeadstartFactory(episode=episode2, team=team)

        self.assertEqual(episode2.headstart_applied(team), puzzle.headstart_granted + headstart.headstart_adjustment)

    def test_next_linear_puzzle(self):
        linear_episode = EpisodeFactory(parallel=False)
        PuzzleFactory.create_batch(10, episode=linear_episode)
        user = UserProfileFactory()
        team = TeamFactory(at_event=linear_episode.event, members=user)

        # TODO: Scramble puzzle order before starting (so they are not in the order they were created).

        # Check we can start and that it is a linear episode.
        self.assertTrue(linear_episode.available(team), msg='Episode is unlocked by team')
        self.assertFalse(linear_episode.parallel, msg='Episode is not set as parallel')

        for i in range(1, linear_episode.puzzle_set.count() + 1):
            # Test we have unlocked the question, but not answered it yet.
            self.assertEqual(linear_episode.next_puzzle(team), i, msg=f'Puzzle[{i}]\'s next puzzle is Puzzle[{i + 1}]')

            # Answer the question and assert that it's now answered.
            GuessFactory.create(for_puzzle=linear_episode.get_puzzle(i), by=user, correct=True)
            self.assertTrue(linear_episode.get_puzzle(i).answered_by(team), msg=f'Correct guess has answered puzzle[{i}]')

    def test_next_parallel_puzzle(self):
        parallel_episode = EpisodeFactory(parallel=True)
        PuzzleFactory.create_batch(10, episode=parallel_episode)
        user = UserProfileFactory()
        team = TeamFactory(at_event=parallel_episode.event, members=user)

        # TODO: Scramble puzzle order before starting (so they are not in the order they were created).

        # Check we can start and that it is a linear episode.
        self.assertTrue(parallel_episode.available(team), msg='Episode is unlocked by team')
        self.assertTrue(parallel_episode.parallel, msg='Episode is not set as parallel')

        # Answer all questions in a random order.
        answer_order = list(range(1, parallel_episode.puzzle_set.count() + 1))
        random.shuffle(answer_order)

        for i in answer_order:
            # Should be no 'next' puzzle for parallel episodes, unless there is just one left.
            # TODO: Check that this is the behaviour that we want, never having a next seems more logical.
            if i != answer_order[-1]:
                self.assertIsNone(parallel_episode.next_puzzle(team), msg='Parallel episode has no next puzzle')
            else:
                self.assertEqual(parallel_episode.next_puzzle(team), i, msg='Last unanswered is next puzzle in parallel episode')

            # Answer the question and assert that it's now answered.
            GuessFactory.create(for_puzzle=parallel_episode.get_puzzle(i), by=user, correct=True)
            self.assertTrue(parallel_episode.get_puzzle(i).answered_by(team), msg=f'Correct guess has answered puzzle[{i}]')
        self.assertIsNone(parallel_episode.next_puzzle(team), msg='Parallel episode has no next puzzle when all puzzles are answered')

    def test_puzzle_numbers(self):
        for episode in EpisodeFactory.create_batch(5):
            for i, puzzle in enumerate(PuzzleFactory.create_batch(5, episode=episode)):
                self.assertEqual(puzzle.get_relative_id(), i + 1, msg='Relative ID should match index in episode')
                self.assertEqual(episode.get_puzzle(puzzle.get_relative_id()), puzzle, msg='A Puzzle\'s relative ID should retrieve it from its Episode')

    def test_upcoming_puzzle_parallel_episode(self):
        with freezegun.freeze_time() as frozen_datetime:
            ep_start = timezone.now() - datetime.timedelta(minutes=60)
            episode = EpisodeFactory(parallel=True, start_date=ep_start)
            num_puzzles = 5
            puzzles = PuzzleFactory.create_batch(
                num_puzzles,
                episode=episode,
                start_date=factory.Iterator([timezone.now() + datetime.timedelta(seconds=i + 1) for i in range(num_puzzles)])
            )
            user = TeamMemberFactory(team__at_event=episode.event)
            self.client.force_login(user.user)
            url = reverse('episode_content', kwargs={'episode_number': episode.get_relative_id()})

            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNotNone(
                upcoming_time,
                'Episode content should set the upcoming puzzle time when no puzzles are visible'
            )
            self.assertEqual(
                upcoming_time,
                timezone.now() + datetime.timedelta(seconds=1),
                'Upcoming puzzle time was incorrect'
            )

            # advance time so we are 0.1 seconds past the first puzzle. The next puzzle is therefore 0.9 seconds away.
            frozen_datetime.tick(datetime.timedelta(seconds=1.1))
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNotNone(
                upcoming_time,
                'Episode content should set the upcoming puzzle time when not all puzzles are visible'
            )
            self.assertEqual(
                upcoming_time,
                timezone.now() + datetime.timedelta(seconds=0.9),
                'Upcoming puzzle time was incorrect'
            )

            # With the first puzzle solved, we will still see an announcement for the second puzzle 0.9 seconds from now.
            GuessFactory(for_puzzle=puzzles[0], by=user, correct=True)
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNotNone(
                upcoming_time,
                'Episode content should set the upcoming puzzle time when no puzzles are visible'
            )
            self.assertEqual(
                upcoming_time,
                timezone.now() + datetime.timedelta(seconds=0.9),
                'Upcoming puzzle time was incorrect'
            )

            # Give the team a headstart of 1.5 seconds, so we are now 0.6 seconds past the second
            # puzzle, and 0.4 away from the third
            HeadstartFactory(
                team=user.team_at(episode.event),
                episode=episode,
                headstart_adjustment=datetime.timedelta(seconds=1.5)
            )
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNotNone(
                upcoming_time,
                'Episode content should set the upcoming puzzle time when no puzzles are visible'
            )
            self.assertEqual(
                upcoming_time, timezone.now() + datetime.timedelta(seconds=0.4),
                'Upcoming puzzle time was incorrect'
            )

            # Advance time for a total of 6 seconds (the time of the final puzzle), so we
            # can see all puzzles and there is no upcoming one
            frozen_datetime.tick(datetime.timedelta(seconds=6.0 - 1.1 - 1.5))
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNone(
                upcoming_time,
                'Episode content should not set the upcoming puzzle time when all puzzles are visible'
            )

    def test_upcoming_puzzle_linear_episode(self):
        with freezegun.freeze_time() as frozen_datetime:
            now = timezone.now()
            ep_start = now - datetime.timedelta(minutes=60)
            episode = EpisodeFactory(parallel=False, start_date=ep_start)
            num_puzzles = 5
            puzzles = PuzzleFactory.create_batch(
                num_puzzles,
                episode=episode,
                start_date=factory.Iterator([now + datetime.timedelta(seconds=i+0.9) for i in range(num_puzzles)])
            )
            user = TeamMemberFactory(team__at_event=episode.event)
            self.client.force_login(user.user)
            url = reverse('episode_content', kwargs={'episode_number': episode.get_relative_id()})

            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNotNone(
                upcoming_time,
                'Episode content should set the upcoming puzzle time when no puzzles are visible'
            )
            self.assertEqual(
                upcoming_time,
                timezone.now() + datetime.timedelta(seconds=0.9),
                'Upcoming puzzle time was incorrect'
            )

            # After 1 second, the first puzzle has started and has not been solved, so the next should not
            # be displayed as "upcoming"
            frozen_datetime.tick(datetime.timedelta(seconds=1))
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNone(
                upcoming_time,
                'Episode content should not set the upcoming puzzle time when the preceding puzzle is unsolved'
            )

            # After solving the first puzzle, the second should be announced
            GuessFactory(by=user, for_puzzle=puzzles[0], correct=True)
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNotNone(
                upcoming_time,
                'Episode content should set the upcoming puzzle time when the preceding puzzle is solved'
            )
            self.assertEqual(
                upcoming_time,
                timezone.now() + datetime.timedelta(seconds=0.9),
                'Upcoming puzzle time was incorrect'
            )

            # Solving the second puzzle, something only an admin can do
            GuessFactory(by=user, for_puzzle=puzzles[1], correct=True)
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNotNone(
                upcoming_time,
                'Episode content should set the upcoming puzzle time when the preceding puzzle is solved'
            )
            self.assertEqual(
                upcoming_time,
                timezone.now() + datetime.timedelta(seconds=1.9),
                'Upcoming puzzle time was incorrect'
            )

            # Adding a headstart so that the next puzzle appears leaves the latest visible puzzle unsolved so again
            # we have no upcoming time.
            HeadstartFactory(
                team=user.team_at(episode.event),
                episode=episode,
                headstart_adjustment=datetime.timedelta(seconds=2.5)
            )
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNone(
                upcoming_time,
                'Episode content should not set the upcoming puzzle time when the preceding puzzle is unsolved'
            )

            for pz in puzzles[2:-1]:
                GuessFactory(by=user, for_puzzle=pz, correct=True)
                upcoming_time = self.client.get(url).context['upcoming_time']
                self.assertIsNotNone(
                    upcoming_time,
                    'Episode content should set the upcoming puzzle time when the preceding puzzle is solved'
                )
                self.assertEqual(
                    upcoming_time,
                    timezone.now() + datetime.timedelta(seconds=0.4),
                    'Upcoming puzzle time was incorrect'
                )

                frozen_datetime.tick(datetime.timedelta(seconds=1))
                upcoming_time = self.client.get(url).context['upcoming_time']
                self.assertIsNone(
                    upcoming_time,
                    'Episode content should not set the upcoming puzzle time when the preceding puzzle is unsolved'
                )

            pz = puzzles[-1]
            GuessFactory(by=user, for_puzzle=pz, correct=True)
            upcoming_time = self.client.get(url).context['upcoming_time']
            self.assertIsNone(
                upcoming_time,
                'Episode content should not set the upcoming puzzle time when all puzzles are solved'
            )


class EpisodeSequenceTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.episode1 = EpisodeFactory(event=self.event)
        self.episode2 = EpisodeFactory(event=self.event, prequels=self.episode1)
        self.user = TeamMemberFactory(team__at_event=self.event)

    def test_episode_prequel_validation(self):
        # Because we intentionally throw exceptions we need to use transaction.atomic() to avoid a TransactionManagementError
        with self.assertRaises(ValidationError), transaction.atomic():
            self.episode1.add_parent(self.episode1)
        with self.assertRaises(ValidationError), transaction.atomic():
            self.episode1.add_parent(self.episode2)

    def test_episode_unlocking(self):
        puzzle = PuzzleFactory(episode=self.episode1)

        self.client.force_login(self.user.user)

        # Can load first episode

        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': self.episode1.get_relative_id()}),
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': self.episode1.get_relative_id()}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)

        # Can't load second episode
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': self.episode2.get_relative_id()}),
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': self.episode2.get_relative_id()}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 403)

        # Can load second episode after event end
        with freezegun.freeze_time() as frozen_datetime:
            frozen_datetime.move_to(self.event.end_date + datetime.timedelta(seconds=1))
            response = self.client.get(
                reverse('episode_content', kwargs={'episode_number': self.episode2.get_relative_id()}),
            )
            self.assertEqual(response.status_code, 200)
            response = self.client.get(
                reverse('episode_content', kwargs={'episode_number': self.episode2.get_relative_id()}),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(response.status_code, 200)

        # Unlock second episode
        GuessFactory(for_puzzle=puzzle, by=self.user, correct=True)

        # Can now load second episode
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': self.episode2.get_relative_id()}),
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': self.episode2.get_relative_id()}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)


class ClueDisplayTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.user = UserProfileFactory()
        self.puzzle = PuzzleFactory(episode=self.episode)
        self.team = TeamFactory(at_event=self.episode.event, members={self.user})
        self.progress = TeamPuzzleProgressFactory(puzzle=self.puzzle, team=self.team)

    def test_hint_display(self):
        hint = HintFactory(puzzle=self.puzzle)

        with freezegun.freeze_time() as frozen_datetime:
            self.progress.start_time = timezone.now()
            self.assertFalse(hint.unlocked_by(self.team, self.progress), "Hint not unlocked by team at start")

            frozen_datetime.tick(hint.time / 2)
            self.assertFalse(hint.unlocked_by(self.team, self.progress), "Hint not unlocked by less than hint time duration.")

            frozen_datetime.tick(hint.time)
            self.assertTrue(hint.unlocked_by(self.team, self.progress), "Hint unlocked by team after required time elapsed.")

    def test_hint_unlocks_at(self):
        hint = HintFactory(puzzle=self.puzzle, time=datetime.timedelta(seconds=42))

        with freezegun.freeze_time() as frozen_datetime:
            now = timezone.now()
            self.progress.start_time = now
            target = now + datetime.timedelta(seconds=42)

            self.assertEqual(hint.unlocks_at(self.team, self.progress), target)
            frozen_datetime.tick(datetime.timedelta(seconds=12))
            self.assertEqual(hint.unlocks_at(self.team, self.progress), target)

        unlock = UnlockFactory(puzzle=self.puzzle)
        hint.start_after = unlock

        with freezegun.freeze_time() as frozen_datetime:
            now = timezone.now()
            self.assertEqual(hint.unlocks_at(self.team, self.progress), None)
            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)
            target = now + datetime.timedelta(seconds=42)

            self.assertEqual(hint.unlocks_at(self.team, self.progress), target)
            frozen_datetime.tick(datetime.timedelta(seconds=12))
            self.assertEqual(hint.unlocks_at(self.team, self.progress), target)

    def test_dependent_hints(self):
        unlock = UnlockFactory(puzzle=self.puzzle)
        hint = HintFactory(puzzle=self.puzzle, start_after=unlock)

        with freezegun.freeze_time() as frozen_datetime:
            self.progress.start_time = timezone.now()
            self.assertFalse(hint.unlocked_by(self.team, self.progress), "Hint unlocked by team at start")

            frozen_datetime.tick(hint.time * 2)
            self.assertFalse(hint.unlocked_by(self.team, self.progress),
                             "Hint unlocked by team when dependent unlock not unlocked.")

            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)
            self.assertFalse(hint.unlocked_by(self.team, self.progress),
                             "Hint unlocked by team as soon as dependent unlock unlocked")

            frozen_datetime.tick(hint.time / 2)
            self.assertFalse(hint.unlocked_by(self.team, self.progress),
                             "Hint unlocked by team before time after dependent unlock was unlocked elapsed")

            frozen_datetime.tick(hint.time)
            self.assertTrue(hint.unlocked_by(self.team, self.progress),
                            "Hint not unlocked by team after time after dependent unlock was unlocked elapsed")

            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)
            self.assertTrue(hint.unlocked_by(self.team, self.progress),
                            "Hint re-locked by subsequent unlock-validating guess!")

            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='NOT_CORRECT')
            self.assertTrue(hint.unlocked_by(self.team, self.progress),
                            "Hint re-locked by subsequent non-unlock-validating guess!")

    def test_unlock_display(self):
        other_team = TeamFactory(at_event=self.episode.event)

        unlock = UnlockFactory(puzzle=self.puzzle)
        GuessFactory.create(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)

        # Check can only be seen by the correct teams.
        self.assertTrue(unlock.unlocked_by(self.team), "Unlock should be visible not it's been guessed")
        self.assertFalse(unlock.unlocked_by(other_team), "Unlock should not be visible to other team")


class FileUploadTests(EventTestCase):
    def setUp(self):
        self.eventfile = EventFileFactory()
        self.user = UserProfileFactory()
        self.client.force_login(self.user.user)

    def test_load_episode_content_with_eventfile(self):
        episode = EpisodeFactory(flavour=f'${{{self.eventfile.slug}}}')
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': episode.get_relative_id()}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.eventfile.file.url)

    def test_load_puzzle_with_eventfile(self):
        puzzle = PuzzleFactory(content=f'${{{self.eventfile.slug}}}')
        response = self.client.get(puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.eventfile.file.url)

    def test_load_puzzle_with_puzzlefile(self):
        puzzle = PuzzleFactory()
        puzzlefile = PuzzleFileFactory(puzzle=puzzle)
        puzzle.content = f'${{{puzzlefile.slug}}}'
        puzzle.save()
        response = self.client.get(puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, puzzlefile.url_path)

    def test_puzzlefile_overrides_eventfile(self):
        puzzle = PuzzleFactory()
        puzzlefile = PuzzleFileFactory(puzzle=puzzle, slug=self.eventfile.slug)
        puzzle.content = f'${{{puzzlefile.slug}}}'
        puzzle.save()
        response = self.client.get(puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, puzzlefile.url_path)

    def test_load_solution_with_eventfile(self):
        puzzle = PuzzleFactory(content='content', soln_content=f'${{{self.eventfile.slug}}}')
        episode_number = puzzle.episode.get_relative_id()
        puzzle_number = puzzle.get_relative_id()
        self.tenant.save()  # To ensure the date we're freezing is correct after any factory manipulation
        with freezegun.freeze_time(self.tenant.end_date + datetime.timedelta(seconds=1)):
            response = self.client.get(
                reverse('solution_content', kwargs={'episode_number': episode_number, 'puzzle_number': puzzle_number}),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.eventfile.file.url)

    def test_load_solution_with_puzzlefile(self):
        puzzle = PuzzleFactory(content='content')
        puzzlefile = PuzzleFileFactory(puzzle=puzzle)
        puzzle.soln_content = f'${{{puzzlefile.slug}}}'
        puzzle.save()
        episode_number = puzzle.episode.get_relative_id()
        puzzle_number = puzzle.get_relative_id()
        self.tenant.save()  # To ensure the date we're freezing is correct after any factory manipulation
        with freezegun.freeze_time(self.tenant.end_date + datetime.timedelta(seconds=1)):
            response = self.client.get(
                reverse('solution_content', kwargs={'episode_number': episode_number, 'puzzle_number': puzzle_number}),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, puzzlefile.url_path)

    def test_load_solution_with_solutionfile(self):
        puzzle = PuzzleFactory(content='content')
        solutionfile = SolutionFileFactory(puzzle=puzzle)
        puzzle.soln_content = f'${{{solutionfile.slug}}}'
        puzzle.save()
        episode_number = puzzle.episode.get_relative_id()
        puzzle_number = puzzle.get_relative_id()
        self.tenant.save()  # To ensure the date we're freezing is correct after any factory manipulation
        with freezegun.freeze_time(self.tenant.end_date + datetime.timedelta(seconds=1)):
            response = self.client.get(
                reverse('solution_content', kwargs={'episode_number': episode_number, 'puzzle_number': puzzle_number}),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, solutionfile.url_path)

    def test_solutionfile_overrides_other_files(self):
        puzzle = PuzzleFactory(content='content')
        puzzlefile = PuzzleFileFactory(puzzle=puzzle, slug=self.eventfile.slug)
        solutionfile = SolutionFileFactory(puzzle=puzzle, slug=puzzlefile.slug)
        puzzle.soln_content = f'${{{solutionfile.slug}}}'
        puzzle.save()
        episode_number = puzzle.episode.get_relative_id()
        puzzle_number = puzzle.get_relative_id()
        self.tenant.save()  # To ensure the date we're freezing is correct after any factory manipulation
        with freezegun.freeze_time(self.tenant.end_date + datetime.timedelta(seconds=1)):
            response = self.client.get(
                reverse('solution_content', kwargs={'episode_number': episode_number, 'puzzle_number': puzzle_number}),
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, solutionfile.url_path)

    def test_file_content_disposition(self):
        puzzle = PuzzleFactory(content='content')
        puzzle_file = PuzzleFileFactory(puzzle=puzzle)
        solution_file = SolutionFileFactory(puzzle=puzzle)
        episode_number = puzzle.episode.get_relative_id()
        puzzle_number = puzzle.get_relative_id()
        response = self.client.get(
            reverse('puzzle_file', kwargs={'episode_number': episode_number, 'puzzle_number': puzzle_number, 'file_path': puzzle_file.url_path})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            path.basename(puzzle_file.file.name),
            response.headers['Content-Disposition'],
            'PuzzleFile response should not include the real filename in Content-Disposition'
        )
        with freezegun.freeze_time(self.tenant.end_date + datetime.timedelta(seconds=1)):
            response = self.client.get(
                reverse('solution_file', kwargs={'episode_number': episode_number, 'puzzle_number': puzzle_number, 'file_path': solution_file.url_path})
            )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            path.basename(solution_file.file.name),
            response.headers['Content-Disposition'],
            'SolutionFile response should not include the real filename in Content-Disposition'
        )


class AdminTeamTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.episode = EpisodeFactory(event=self.event)
        self.admin_user = UserProfileFactory()
        self.admin_team = TeamFactory(at_event=self.event, role=TeamRole.ADMIN, members={self.admin_user})

    def test_can_view_episode(self):
        self.client.force_login(self.admin_user.user)
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': self.episode.get_relative_id()}),
        )
        self.assertEqual(response.status_code, 200)

    def test_can_view_guesses(self):
        self.client.force_login(self.admin_user.user)
        response = self.client.get(reverse('admin_guesses'))
        self.assertEqual(response.status_code, 200)

    def test_can_view_stats(self):
        self.client.force_login(self.admin_user.user)
        response = self.client.get(reverse('admin_guesses'))
        self.assertEqual(response.status_code, 200)


class AdminContentTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory(event=self.tenant)
        self.admin_user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN)
        self.admin_team = self.admin_user.team_at(self.tenant)
        self.puzzle = PuzzleFactory(episode=self.episode, start_date=None)
        self.guesses = GuessFactory.create_batch(5, for_puzzle=self.puzzle)
        self.guesses_url = reverse('admin_guesses_list')

    def test_can_view_guesses(self):
        self.client.force_login(self.admin_user.user)
        response = self.client.get(self.guesses_url)
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_view_guesses(self):
        player = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.PLAYER)
        self.client.force_login(player.user)
        response = self.client.get(reverse('admin_guesses'))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_guesses_list'))
        self.assertEqual(response.status_code, 403)

    def test_can_view_guesses_by_team(self):
        team_id = self.guesses[0].by_team.id
        self.client.force_login(self.admin_user.user)
        response = self.client.get(f'{self.guesses_url}?team={team_id}')
        self.assertEqual(response.status_code, 200)

    def test_can_view_guesses_by_puzzle(self):
        puzzle_id = self.guesses[0].for_puzzle.id
        self.client.force_login(self.admin_user.user)
        response = self.client.get(f'{self.guesses_url}?puzzle={puzzle_id}')
        self.assertEqual(response.status_code, 200)

    def test_can_view_guesses_by_episode(self):
        episode_id = self.guesses[0].for_puzzle.episode.id
        self.client.force_login(self.admin_user.user)
        response = self.client.get(f'{self.guesses_url}?episode={episode_id}')
        self.assertEqual(response.status_code, 200)

    def test_can_view_stats(self):
        stats_url = reverse('admin_stats')
        self.client.force_login(self.admin_user.user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 200)

    def test_can_view_stats_content(self):
        stats_url = reverse('admin_stats_content')
        self.client.force_login(self.admin_user.user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 200)

    def test_can_view_stats_content_by_episode(self):
        episode_id = self.guesses[0].for_puzzle.episode.id
        stats_url = reverse('admin_stats_content', kwargs={'episode_id': episode_id})
        self.client.force_login(self.admin_user.user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_view_stats(self):
        player = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.PLAYER)
        self.client.force_login(player.user)
        response = self.client.get(reverse('admin_stats'))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_stats_content'))
        self.assertEqual(response.status_code, 403)

    def test_non_admin_cannot_view_admin_team(self):
        player = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.PLAYER)
        self.client.force_login(player.user)
        response = self.client.get(reverse('admin_team'))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_team_detail', kwargs={'team_id': self.admin_team.id}))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_team_detail_content', kwargs={'team_id': self.admin_team.id}))
        self.assertEqual(response.status_code, 403)

    def test_admin_team_detail_not_found(self):
        self.client.force_login(self.admin_user.user)
        response = self.client.get(reverse('admin_team_detail', kwargs={'team_id': 0}))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse('admin_team_detail_content', kwargs={'team_id': 0}))
        self.assertEqual(response.status_code, 404)

    def test_can_view_admin_team(self):
        self.client.force_login(self.admin_user.user)
        url = reverse('admin_team')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_team.get_verbose_name())

    def test_can_view_admin_team_detail(self):
        self.client.force_login(self.admin_user.user)
        url = reverse('admin_team_detail', kwargs={'team_id': self.admin_team.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_team.get_verbose_name())

    def test_admin_team_detail_content(self):
        team = self.guesses[0].by_team
        puzzle2 = PuzzleFactory()
        GuessFactory(by=team.members.all()[0], for_puzzle=puzzle2, correct=True)

        self.client.force_login(self.admin_user.user)
        url = reverse('admin_team_detail_content', kwargs={'team_id': team.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_json = response.json()

        self.assertTrue('puzzles' in response_json)
        self.assertEqual(len(response_json['puzzles']), 1)
        self.assertEqual(response_json['puzzles'][0]['id'], self.puzzle.id)
        self.assertEqual(len(response_json['puzzles'][0]['guesses']), 1)

        self.assertTrue('solved_puzzles' in response_json)
        self.assertEqual(len(response_json['solved_puzzles']), 1)
        self.assertEqual(response_json['solved_puzzles'][0]['id'], puzzle2.id)
        self.assertEqual(response_json['puzzles'][0]['num_guesses'], 1)

    def test_admin_team_detail_content_guesses(self):
        # Create a user/team that's made >5 guesses
        user = TeamMemberFactory(team__at_event=self.tenant)
        team = user.team_at(self.tenant)
        now = timezone.now()
        # We have to make the TeamPuzzleProgress before the guesses since Guess does a `get_or_create` in a `post_save` signal
        TeamPuzzleProgressFactory(team=team, puzzle=self.puzzle, start_time=timezone.now() - datetime.timedelta(minutes=20))
        guesses = GuessFactory.create_batch(10, for_puzzle=self.puzzle, by=user)
        # The guesses get forced to the current time when created, we have to override afterwards
        for i, guess in enumerate(guesses):
            guess.given = now - datetime.timedelta(minutes=i)
            guess.save()

        self.client.force_login(self.admin_user.user)
        url = reverse('admin_team_detail_content', kwargs={'team_id': team.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response_json = response.json()

        self.assertTrue('puzzles' in response_json)
        self.assertEqual(len(response_json['puzzles']), 1)
        self.assertEqual(response_json['puzzles'][0]['id'], self.puzzle.id)
        self.assertEqual(response_json['puzzles'][0]['guesses'], [{
            'user': guess.by.username,
            'guess': guess.guess,
            'given': guess.given.isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        } for guess in guesses[:5]])

    def test_admin_team_detail_content_hints(self):
        team = self.guesses[0].by_team
        member = self.guesses[0].by
        self.client.force_login(self.admin_user.user)
        url = reverse('admin_team_detail_content', kwargs={'team_id': team.id})

        with freezegun.freeze_time() as frozen_datetime:
            TeamPuzzleProgress.objects.get(team=team, puzzle=self.puzzle)

            hint = HintFactory(puzzle=self.puzzle, time=datetime.timedelta(minutes=10), start_after=None)

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response_json = response.json()

            # Initially the hint is not unlocked, but scheduled
            self.assertEqual(len(response_json['puzzles'][0]['clues_visible']), 0)
            self.assertEqual(len(response_json['puzzles'][0]['hints_scheduled']), 1)
            self.assertEqual(response_json['puzzles'][0]['hints_scheduled'][0]['text'], hint.text)

            # Advance time and retry; now the hint should show as unlocked (and not scheduled).
            frozen_datetime.tick(datetime.timedelta(minutes=11))

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response_json = response.json()

            self.assertEqual(len(response_json['puzzles'][0]['clues_visible']), 1)
            self.assertEqual(len(response_json['puzzles'][0]['hints_scheduled']), 0)
            self.assertEqual(response_json['puzzles'][0]['clues_visible'][0]['text'], hint.text)

            # Make the hint dependent on an unlock that is not unlocked. It is now neither visible nor scheduled.
            unlock = UnlockFactory(puzzle=self.puzzle)
            hint.start_after = unlock
            hint.save()

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response_json = response.json()

            self.assertEqual(len(response_json['puzzles'][0]['clues_visible']), 0)
            self.assertEqual(len(response_json['puzzles'][0]['hints_scheduled']), 0)

            # Add a guess which unlocks the unlock, the hint should now again be scheduled
            GuessFactory(for_puzzle=self.puzzle, by=member, guess=unlock.unlockanswer_set.all()[0].guess)

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response_json = response.json()

            self.assertEqual(len(response_json['puzzles'][0]['clues_visible']), 1)
            self.assertEqual(len(response_json['puzzles'][0]['hints_scheduled']), 1)
            self.assertEqual(response_json['puzzles'][0]['hints_scheduled'][0]['text'], hint.text)

            # Advance time again, the hint should now be visible, alongside the unlock
            frozen_datetime.tick(datetime.timedelta(minutes=11))
            # Add another guess to ensure this doesn't throw off the timings
            GuessFactory(for_puzzle=self.puzzle, by=member, guess=unlock.unlockanswer_set.all()[0].guess)

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response_json = response.json()

            # TODO disambiguate?
            self.assertEqual(len(response_json['puzzles'][0]['clues_visible']), 2)
            self.assertEqual(len(response_json['puzzles'][0]['hints_scheduled']), 0)
            self.assertEqual(response_json['puzzles'][0]['clues_visible'][1]['text'], hint.text)

    def test_can_view_admin_progress(self):
        self.client.force_login(self.admin_user.user)
        url = reverse('admin_progress')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_view_admin_progress(self):
        player = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.PLAYER)
        self.client.force_login(player.user)
        response = self.client.get(reverse('admin_progress'))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_progress_content'))
        self.assertEqual(response.status_code, 403)

    def _check_team_get_progress(self, response, team):
        data = [x for x in response.json()['team_progress'] if x['id'] == team.id]
        self.assertEqual(len(data), 1)
        data = data[0]
        self.assertEqual(data['name'], team.name)
        self.assertEqual(data['url'], reverse('admin_team_detail', kwargs={'team_id': team.id}))

        return data['progress']

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_admin_progress_content(self):
        with freezegun.freeze_time() as frozen_datetime:
            team1 = self.guesses[0].by_team
            team2 = self.guesses[1].by_team
            tpp1 = TeamPuzzleProgress.objects.get(team=team1, puzzle=self.puzzle)
            tpp1.start_time = timezone.now()
            tpp1.save()
            tpp2 = TeamPuzzleProgress.objects.get(team=team2, puzzle=self.puzzle)
            tpp2.start_time = timezone.now()
            tpp2.save()
            # tpp1 = TeamPuzzleProgressFactory(team=team1, puzzle=self.puzzle)
            frozen_datetime.tick(datetime.timedelta(minutes=1))

            # Add a guess by an admin to confirm they don't appear
            GuessFactory(by=self.admin_user, by_team=self.admin_team, for_puzzle=self.puzzle)
            GuessFactory(by=team2.members.all()[0], for_puzzle=self.puzzle, correct=True)
            # Add a team which has done nothing and therefore will not show up
            team3 = TeamPuzzleProgressFactory(puzzle=self.puzzle).team

            self.client.force_login(self.admin_user.user)
            url = reverse('admin_progress_content')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            content = response.json()
            self.assertEqual(len(content['puzzles']), 1)
            self.assertEqual(content['puzzles'][0]['title'], self.puzzle.title)

            self.assertEqual(len(content['team_progress']), 5)

            # team1 has opened the puzzle and made an incorrect guess
            team1_data = self._check_team_get_progress(response, team1)
            self.assertEqual(team1_data[0]['puzzle_id'], self.puzzle.id)
            self.assertEqual(team1_data[0]['state'], 'open')
            self.assertEqual(team1_data[0]['guesses'], 1)
            self.assertEqual(team1_data[0]['time_on'], 60)
            self.assertIsNotNone(team1_data[0]['latest_guess'])
            # Django's JSON encoder truncates the microseconds to milliseconds
            latest_guess = datetime.datetime.fromisoformat(team1_data[0]['latest_guess'].replace('Z', '+00:00'))
            diff = abs(latest_guess - self.guesses[0].given).total_seconds()
            self.assertTrue(diff < 0.001)

            # team2 has opened the puzzle and made a correct guess
            # move time forwards to verify that time_on is the solve time
            frozen_datetime.tick(datetime.timedelta(minutes=1))
            team2_data = self._check_team_get_progress(response, team2)
            self.assertEqual(team2_data[0]['puzzle_id'], self.puzzle.id)
            self.assertEqual(team2_data[0]['state'], 'solved')
            self.assertEqual(team2_data[0]['guesses'], 2)
            self.assertEqual(team2_data[0]['time_on'], 60)
            self.assertIsNone(team2_data[0]['latest_guess'])

            # team3 has opened the puzzle and made no guesses
            self.assertFalse(any([True for x in response.json()['team_progress'] if x['id'] == team3.id]))

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_admin_progress_content_hints(self):
        team = self.guesses[0].by_team
        member = self.guesses[0].by
        self.client.force_login(self.admin_user.user)

        url = reverse('admin_progress_content')

        with freezegun.freeze_time() as frozen_datetime:
            TeamPuzzleProgressFactory(team=team, puzzle=self.puzzle, start_time=timezone.now())
            hint = HintFactory(puzzle=self.puzzle, time=datetime.timedelta(minutes=10), start_after=None)

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            progress = self._check_team_get_progress(response, team)

            # Initially the hint is not unlocked, but scheduled
            self.assertTrue(progress[0]['hints_scheduled'])

            # Advance time and retry; now no hints are scheduled again
            frozen_datetime.tick(datetime.timedelta(minutes=11))

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            progress = self._check_team_get_progress(response, team)
            self.assertFalse(progress[0]['hints_scheduled'])

            # Make the hint dependent on an unlock that is not unlocked. It should remain unscheduled.
            unlock = UnlockFactory(puzzle=self.puzzle)
            hint.start_after = unlock
            hint.save()

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            progress = self._check_team_get_progress(response, team)
            self.assertFalse(progress[0]['hints_scheduled'])

            # Unlock the unlock, it should now be scheduled again
            GuessFactory(for_puzzle=self.puzzle, by=member, guess=unlock.unlockanswer_set.all()[0].guess)

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            progress = self._check_team_get_progress(response, team)
            self.assertTrue(progress[0]['hints_scheduled'])

    def test_non_admin_cant_reset_progress(self):
        player = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.PLAYER)
        self.client.force_login(player.user)

        url = reverse('reset_progress') + f'?team={player.team_at(self.tenant).id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_reset_progress(self):
        self.client.force_login(self.admin_user.user)

        url = reverse('reset_progress') + f'?team={self.admin_team.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)

    def test_reset_progress_resets_progress(self):
        player = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.PLAYER)
        team = player.team_at(self.tenant)

        # We are going to first reset progress on a specific puzzle and check that the following
        # all disappears
        tpp_1 = TeamPuzzleProgressFactory(team=self.admin_team)
        GuessFactory(for_puzzle=tpp_1.puzzle, by_team=self.admin_team)
        UnlockAnswerFactory(unlock__puzzle=tpp_1.puzzle, guess='__UNLOCK__')
        GuessFactory(for_puzzle=tpp_1.puzzle, by_team=self.admin_team, guess='__UNLOCK__')
        TeamPuzzleDataFactory(team=self.admin_team, puzzle=tpp_1.puzzle)
        UserPuzzleDataFactory(user=self.admin_user, puzzle=tpp_1.puzzle)

        # We will check that all of the following still exists. Then we will delete all progress
        # for the admin team and check it is gone.
        tpp_2 = TeamPuzzleProgressFactory(team=self.admin_team)
        GuessFactory(for_puzzle=tpp_2.puzzle, by_team=self.admin_team)
        UnlockAnswerFactory(unlock__puzzle=tpp_2.puzzle, guess='__UNLOCK__')
        GuessFactory(for_puzzle=tpp_2.puzzle, by_team=self.admin_team, guess='__UNLOCK__')
        TeamPuzzleDataFactory(team=self.admin_team, puzzle=tpp_2.puzzle)
        UserPuzzleDataFactory(user=self.admin_user, puzzle=tpp_2.puzzle)

        # In the meantime we will check that all of this other data isn't deleted
        tpp_player = TeamPuzzleProgressFactory(team=team)
        GuessFactory(for_puzzle=tpp_player.puzzle, by_team=team)
        UnlockAnswerFactory(unlock__puzzle=tpp_player.puzzle, guess='__UNLOCK__')
        GuessFactory(for_puzzle=tpp_player.puzzle, by_team=team, guess='__UNLOCK__')
        TeamPuzzleDataFactory(team=team, puzzle=tpp_player.puzzle)
        UserPuzzleDataFactory(user=player, puzzle=tpp_player.puzzle)

        self.client.force_login(self.admin_user.user)
        url = reverse('reset_progress') + f'?team={self.admin_team.id}&puzzle={tpp_1.puzzle.id}'
        response = self.client.post(
            url,
            {'confirm': True, 'is_player_team_ok': True, 'event_over_ok': True, 'event_in_progress_ok': True}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Guess.objects.filter(by_team=self.admin_team, for_puzzle=tpp_1.puzzle).count(), 0)
        self.assertEqual(TeamPuzzleProgress.objects.filter(team=self.admin_team, puzzle=tpp_1.puzzle).count(), 0)
        self.assertEqual(TeamUnlock.objects.filter(team_puzzle_progress__team=self.admin_team, team_puzzle_progress__puzzle=tpp_1.puzzle).count(), 0)
        self.assertEqual(TeamPuzzleData.objects.filter(team=self.admin_team, puzzle=tpp_1.puzzle).count(), 0)
        self.assertEqual(UserPuzzleData.objects.filter(user__in=self.admin_team.members.all(), puzzle=tpp_1.puzzle).count(), 0)

        self.assertGreater(Guess.objects.filter(by_team=self.admin_team).count(), 0)
        self.assertGreater(TeamPuzzleProgress.objects.filter(team=self.admin_team).count(), 0)
        self.assertGreater(TeamUnlock.objects.filter(team_puzzle_progress__team=self.admin_team).count(), 0)
        self.assertGreater(TeamPuzzleData.objects.filter(team=self.admin_team).count(), 0)
        self.assertGreater(UserPuzzleData.objects.filter(user__in=self.admin_team.members.all()).count(), 0)

        url = reverse('reset_progress') + f'?team={self.admin_team.id}'
        response = self.client.post(
            url,
            {'confirm': True, 'is_player_team_ok': True, 'event_over_ok': True, 'event_in_progress_ok': True}
        )
        self.assertEqual(response.status_code, 302)

        self.assertEqual(Guess.objects.filter(by_team=self.admin_team).count(), 0)
        self.assertEqual(TeamPuzzleProgress.objects.filter(team=self.admin_team).count(), 0)
        self.assertEqual(TeamUnlock.objects.filter(team_puzzle_progress__team=self.admin_team).count(), 0)
        self.assertEqual(TeamPuzzleData.objects.filter(team=self.admin_team).count(), 0)
        self.assertEqual(UserPuzzleData.objects.filter(user__in=self.admin_team.members.all()).count(), 0)

        self.assertGreater(Guess.objects.filter(by_team=team).count(), 0)
        self.assertGreater(TeamPuzzleProgress.objects.filter(team=team).count(), 0)
        self.assertGreater(TeamUnlock.objects.filter(team_puzzle_progress__team=team).count(), 0)
        self.assertGreater(TeamPuzzleData.objects.filter(team=team).count(), 0)
        self.assertGreater(UserPuzzleData.objects.filter(user__in=team.members.all()).count(), 0)

    def test_reset_progress_warnings(self):
        self.client.force_login(self.admin_user.user)
        player_team = TeamFactory(role=TeamRole.PLAYER)

        self.episode.start_date = timezone.now() + datetime.timedelta(days=1)
        self.episode.save()
        url = reverse('reset_progress') + f'?team={player_team.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode(response.charset)
        self.assertIn('the team is a player team', content)
        self.assertNotIn('the event is in progress', content)
        self.assertNotIn('the event is over', content)

        url = reverse('reset_progress') + f'?team={self.admin_team.id}'

        self.episode.start_date = timezone.now() - datetime.timedelta(days=1)
        self.episode.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode(response.charset)
        self.assertNotIn('the team is a player team', content)
        self.assertIn('the event is in progress', content)
        self.assertNotIn('the event is over', content)

        self.episode.start_date = timezone.now() + datetime.timedelta(days=1)
        self.episode.save()
        self.tenant.end_date = timezone.now() - datetime.timedelta(days=1)
        self.tenant.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode(response.charset)
        self.assertNotIn('the team is a player team', content)
        self.assertNotIn('the event is in progress', content)
        self.assertIn('the event is over', content)

        self.tenant.end_date = timezone.now() + datetime.timedelta(days=1)
        self.tenant.save()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode(response.charset)
        self.assertNotIn('the team is a player team', content)
        self.assertNotIn('the event is in progress', content)
        self.assertNotIn('the event is over', content)


class StatsTests(EventTestCase):
    def setUp(self):
        self.admin_user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN)

    def test_no_episodes(self):
        stats_url = reverse('admin_stats_content')
        self.client.force_login(self.admin_user.user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 404)

    def test_filter_invalid_episode(self):
        episode = EpisodeFactory(event=self.tenant)
        # The next sequantial ID ought to not exist
        stats_url = reverse('admin_stats_content', kwargs={'episode_id': episode.id + 1})
        self.client.force_login(self.admin_user.user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 404)


class ProgressionTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.event = self.episode.event
        self.user1 = UserProfileFactory()
        self.user2 = UserProfileFactory()
        self.team1 = TeamFactory(at_event=self.event, members={self.user1})
        self.team2 = TeamFactory(at_event=self.event, members={self.user2})

    def test_episode_finishing(self):
        # Ensure at least one puzzle in episode.
        puzzles = PuzzleFactory.create_batch(3, episode=self.episode)
        sequel = EpisodeFactory(prequels=[self.episode])

        # Check episode has not been completed
        self.assertTrue(self.episode.available(self.team1))
        self.assertFalse(sequel.available(self.team1))

        # Team 1 answer all questions correctly
        for puzzle in puzzles:
            GuessFactory.create(for_puzzle=puzzle, by=self.user1, correct=True)

        # Ensure this team has finished the episode (i.e. can guess on the next one)
        self.assertTrue(sequel.available(self.team1))

    def test_finish_positions(self):
        puzzle1, puzzle2, puzzle3 = PuzzleFactory.create_batch(3, episode=self.episode)

        # Check there are no winners to begin with
        self.assertEqual(len(self.episode.finished_positions()), 0)

        # Answer all the questions correctly for both teams with team 1 ahead to begin with then falling behind
        GuessFactory.create(for_puzzle=puzzle1, by=self.user1, correct=True)
        GuessFactory.create(for_puzzle=puzzle2, by=self.user1, correct=True)

        # Check only the first team has finished the first questions
        self.assertEqual(len(puzzle1.finished_teams()), 1)
        self.assertEqual(puzzle1.finished_teams()[0], self.team1)
        self.assertEqual(puzzle1.position(self.team1), 0)
        self.assertEqual(puzzle1.position(self.team2), None)

        # Team 2 completes all answers
        GuessFactory.create(for_puzzle=puzzle1, by=self.user2, correct=True)
        GuessFactory.create(for_puzzle=puzzle2, by=self.user2, correct=True)
        GuessFactory.create(for_puzzle=puzzle3, by=self.user2, correct=True)

        # Ensure this team has finished the questions and is listed as first in the finished teams
        self.assertEqual(len(self.episode.finished_positions()), 1)
        self.assertEqual(self.episode.finished_positions()[0], self.team2)

        # Team 1 finishes as well.
        GuessFactory(for_puzzle=puzzle3, by=self.user1, correct=True)

        # Ensure both teams have finished, and are ordered correctly
        self.assertEqual(len(self.episode.finished_positions()), 2)
        self.assertEqual(self.episode.finished_positions()[0], self.team2)
        self.assertEqual(self.episode.finished_positions()[1], self.team1)

    def test_guesses(self):
        puzzle1 = PuzzleFactory(episode=self.episode)

        # Single incorrect guess
        GuessFactory(for_puzzle=puzzle1, by=self.user1, correct=False)

        # Check we have no correct answers
        self.assertEqual(len(puzzle1.first_correct_guesses(self.event)), 0)

        # Add two correct guesses after each other
        with freezegun.freeze_time() as frozen_datetime:
            first_correct_guess = GuessFactory(for_puzzle=puzzle1, by=self.user1, correct=True)
            frozen_datetime.tick(datetime.timedelta(hours=1))
            GuessFactory.create(for_puzzle=puzzle1, by=self.user1, correct=True)

        # Ensure that the first correct guess is correctly returned
        self.assertEqual(puzzle1.first_correct_guesses(self.event)[self.team1], first_correct_guess)


class ProgressSignalTests(EventTestCase):
    def setUp(self):
        self.answer = AnswerFactory(runtime=Runtime.REGEX, answer=r'correct\d')
        self.puzzle = self.answer.for_puzzle
        self.unlockanswer = UnlockAnswerFactory(unlock__puzzle=self.puzzle, runtime=Runtime.REGEX, guess=r'unlock\d')
        self.unlock = self.unlockanswer.unlock
        self.user = TeamMemberFactory()
        self.team = self.user.team_at(self.tenant)
        self.progress = TeamPuzzleProgress(team=self.team, puzzle=self.puzzle, start_time=timezone.now())
        self.progress.save()

    def test_save_guess_updates_progress_correctly(self):
        GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='incorrect')
        self.assertIsNone(TeamPuzzleProgress.objects.get(team=self.team, puzzle=self.puzzle).solved_by,
                          'Incorrect guess resulted in puzzle marked as solved')
        self.assertFalse(TeamUnlock.objects.filter(team_puzzle_progress=self.progress, unlockanswer=self.unlockanswer).exists(),
                         'Non-unlocking guess resulted in unlock being marked as unlocked')
        GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        self.assertTrue(TeamPuzzleProgress.objects.get(team=self.team, puzzle=self.puzzle).solved_by,
                        'Correct guess resulted in puzzle marked as not solved')
        GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='unlock0')
        self.assertTrue(TeamUnlock.objects.filter(team_puzzle_progress=self.progress, unlockanswer=self.unlockanswer).exists(),
                        'Unlocking guess did not result in unlock being marked as unlocked')

    def test_add_answer_updates_progress(self):
        guessa = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correcta')
        self.progress.refresh_from_db()
        self.assertIsNone(self.progress.solved_by)
        AnswerFactory(for_puzzle=self.puzzle, runtime=Runtime.REGEX, answer=r'correct.')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guessa)

    def test_add_answer_doesnt_update_solved_puzzle(self):
        GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correcta')
        guess2 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)
        AnswerFactory(for_puzzle=self.puzzle, runtime=Runtime.REGEX, answer=r'correct.')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)

    def test_modify_answer_doesnt_update_solved_puzzle_when_still_solved(self):
        GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correcta')
        guess2 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)
        self.answer.answer = 'correct.'
        self.answer.save()
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)

    def test_modify_answer_updates_solved_puzzle_when_still_solved(self):
        self.answer.answer = 'correct.'
        self.answer.save()
        guess1 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correcta')
        guess2 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess1)
        self.answer.answer = r'correct\d'
        self.answer.save()
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)

    def test_modify_answer_unsolves_puzzle(self):
        guess = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess)
        self.answer.answer = 'correct'
        self.answer.save()
        self.progress.refresh_from_db()
        self.assertIsNone(self.progress.solved_by)

    def test_modify_answer_solves_puzzle(self):
        guess = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correcta')
        self.progress.refresh_from_db()
        self.assertIsNone(self.progress.solved_by)
        self.answer.answer = 'correct.'
        self.answer.save()
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess)

    def test_delete_answer_unsolves_puzzle(self):
        guess = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess)
        self.answer.delete()
        self.progress.refresh_from_db()
        self.assertIsNone(self.progress.solved_by)

    def test_delete_answer_doesnt_change_solved_by(self):
        GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct_0')
        guess2 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct1')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)
        AnswerFactory(for_puzzle=self.puzzle, runtime=Runtime.REGEX, answer=r'correct.?\d')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)
        self.answer.delete()
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)

    def test_delete_answer_changes_solved_by(self):
        guess1 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        guess2 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct1')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess1)
        AnswerFactory(for_puzzle=self.puzzle, runtime=Runtime.STATIC, answer='correct1')
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess1)
        self.answer.delete()
        self.progress.refresh_from_db()
        self.assertEqual(self.progress.solved_by, guess2)

    def do_reevaluate(self):
        self.progress.reevaluate(Answer.objects.all(), Guess.objects.all().order_by('given'))
        self.progress.save()

    def test_progress_reevaluation(self):
        # TODO name of testcase
        # TODO split?
        GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='incorrect')
        self.do_reevaluate()
        # incorrect guess -> not solved
        self.assertIsNone(self.progress.solved_by)
        guess0 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct0')
        self.do_reevaluate()
        # guess correct by orig answer -> solved by that guess
        self.assertEqual(self.progress.solved_by, guess0)
        self.answer.answer = r'correct_\d'
        self.answer.save()
        self.do_reevaluate()
        # change that answer -> not solved
        self.assertIsNone(self.progress.solved_by)
        guess1 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct_1')
        self.do_reevaluate()
        # add guess which works with modified answer -> solved by new guess
        self.assertEqual(self.progress.solved_by, guess1)
        newanswer = AnswerFactory(for_puzzle=self.puzzle, runtime=Runtime.REGEX, answer=r'correct\d')
        self.do_reevaluate()
        # two answers, one validating the original guess -> solved by first guess
        self.assertEqual(self.progress.solved_by, guess0)
        guess2 = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='correct2')
        self.do_reevaluate()
        # add a third correct guess -> still solved by first guess
        self.assertEqual(self.progress.solved_by, guess0)
        guess0.delete()
        self.do_reevaluate()
        # delete oldest correct guess -> solved by next oldest correct guess
        self.assertEqual(self.progress.solved_by, guess1)
        guess1.delete()
        self.do_reevaluate()
        # delete next oldest -> same
        self.assertEqual(self.progress.solved_by, guess2)
        newanswer.delete()
        self.do_reevaluate()
        # delete answer which validated last guess -> not solved
        self.assertIsNone(self.progress.solved_by)
        # scenarios covered:
        # one / two answers; zero-three correct guesses.

    def test_add_unlockanswer_adds_teamunlock(self):
        guess = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='unlock_0')
        self.assertFalse(TeamUnlock.objects.filter(team_puzzle_progress=self.progress).exists(),
                         'Non-unlocking guess resulted in a TeamUnlock being created')
        ua = UnlockAnswerFactory(unlock=self.unlock, runtime=Runtime.REGEX, guess=r'unlock_\d')
        self.assertTrue(TeamUnlock.objects.filter(team_puzzle_progress=self.progress, unlocked_by=guess, unlockanswer=ua).exists(),
                        'Unlocking guess did not result in unlock being marked as unlocked')

    def test_modify_unlockanswer_creates_teamunlock(self):
        guess = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='unlock_0')
        self.assertFalse(TeamUnlock.objects.filter(team_puzzle_progress=self.progress).exists(),
                         'Non-unlocking guess resulted in a TeamUnlock being created')
        self.unlockanswer.guess = r'unlock_\d'
        self.unlockanswer.save()
        self.assertTrue(TeamUnlock.objects.filter(team_puzzle_progress=self.progress, unlocked_by=guess, unlockanswer=self.unlockanswer).exists(),
                        'Unlocking guess did not result in unlock being marked as unlocked')

    def test_modify_unlockanswer_deletes_teamunlock(self):
        guess = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='unlock0')
        self.assertTrue(TeamUnlock.objects.filter(team_puzzle_progress=self.progress, unlocked_by=guess, unlockanswer=self.unlockanswer).exists(),
                        'Unlocking guess did not result in unlock being marked as unlocked')
        self.unlockanswer.guess = r'unlock_\d'
        self.unlockanswer.save()
        self.assertFalse(TeamUnlock.objects.filter(team_puzzle_progress=self.progress).exists(),
                         'Non-unlocking guess resulted in a TeamUnlock being created')

    def test_delete_unlockanswer_deletes_teamunlock(self):
        guess = GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='unlock0')
        self.assertTrue(TeamUnlock.objects.filter(team_puzzle_progress=self.progress, unlocked_by=guess, unlockanswer=self.unlockanswer).exists(),
                        'Unlocking guess did not result in unlock being marked as unlocked')
        self.unlockanswer.delete()
        self.assertFalse(TeamUnlock.objects.filter(team_puzzle_progress=self.progress).exists(),
                         'Non-unlocking guess resulted in a TeamUnlock being created')


class EventWinningTests(EventTestCase):
    fixtures = ["teams_test"]

    def setUp(self):
        self.ep1 = EpisodeFactory(winning=True)
        self.ep2 = EpisodeFactory(winning=False)
        self.user1 = UserProfileFactory()
        self.user2 = UserProfileFactory()
        self.team1 = TeamFactory(members=self.user1)
        self.team2 = TeamFactory(members=self.user2)

        PuzzleFactory.create_batch(2, episode=self.ep1)
        PuzzleFactory.create_batch(2, episode=self.ep2)

    def test_win_single_linear_episode(self):
        # No correct answers => noone has finished => no finishing positions!
        self.assertEqual(utils.finishing_positions(self.tenant), [])

        GuessFactory.create(for_puzzle=self.ep1.get_puzzle(1), by=self.user1, correct=True)
        GuessFactory.create(for_puzzle=self.ep1.get_puzzle(1), by=self.user2, correct=True)
        # First episode still not complete
        self.assertEqual(utils.finishing_positions(self.tenant), [])

        g = GuessFactory.create(for_puzzle=self.ep1.get_puzzle(2), by=self.user1, correct=True)
        GuessFactory.create(for_puzzle=self.ep1.get_puzzle(2), by=self.user2, correct=False)
        # Team 1 has finished the only winning episode, but Team 2 has not
        self.assertEqual(utils.finishing_positions(self.tenant), [self.team1])

        GuessFactory.create(for_puzzle=self.ep1.get_puzzle(2), by=self.user2, correct=True)
        # Team 2 should now be second place
        self.assertEqual(utils.finishing_positions(self.tenant), [self.team1, self.team2])

        # Make sure the order changes correctly
        g.given = timezone.now()
        g.save()
        self.assertEqual(utils.finishing_positions(self.tenant), [self.team2, self.team1])

    def test_win_two_linear_episodes(self):
        self.ep2.winning = True
        self.ep2.save()

        self.assertEqual(utils.finishing_positions(self.tenant), [])

        for pz in self.ep1.puzzle_set.all():
            for user in (self.user1, self.user2):
                GuessFactory.create(for_puzzle=pz, by=user, correct=True)
        # We need to complete both episodes
        self.assertEqual(utils.finishing_positions(self.tenant), [])

        # both teams complete episode 2, but now their episode 1 guesses are wrong
        for pz in self.ep1.puzzle_set.all():
            for g in pz.guess_set.all():
                g.delete()
        for pz in self.ep1.puzzle_set.all():
            for user in (self.user1, self.user2):
                GuessFactory.create(for_puzzle=pz, by=user, correct=False)

        for pz in self.ep2.puzzle_set.all():
            for user in (self.user1, self.user2):
                GuessFactory.create(for_puzzle=pz, by=user, correct=True)
        # Should still have no-one finished
        self.assertEqual(utils.finishing_positions(self.tenant), [])

        # Make correct Episode 1 guesses again
        for pz in self.ep1.puzzle_set.all() | self.ep2.puzzle_set.all():
            for g in pz.guess_set.all():
                g.delete()
            for user in (self.user1, self.user2):
                GuessFactory.create(for_puzzle=pz, by=user, correct=True)
        # Now both teams should have finished, with team1 first
        self.assertEqual(utils.finishing_positions(self.tenant), [self.team1, self.team2])

        # Swap order
        for pz in self.ep1.puzzle_set.all():
            for g in pz.guess_set.filter(by=self.user1):
                g.given = timezone.now()
                g.save()
        # team2 should be first
        self.assertEqual(utils.finishing_positions(self.tenant), [self.team2, self.team1])


class CorrectnessCacheTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.event = self.episode.event
        self.user1 = UserProfileFactory()
        self.user2 = UserProfileFactory()
        self.team1 = TeamFactory(at_event=self.event, members={self.user1})
        self.team2 = TeamFactory(at_event=self.event, members={self.user2})
        self.puzzle1 = PuzzleFactory(episode=self.episode)
        self.puzzle2 = PuzzleFactory(episode=self.episode)
        self.answer1 = self.puzzle1.answer_set.get()

    def test_changing_answers(self):
        # Check starting state
        self.assertFalse(self.puzzle1.answered_by(self.team1))
        self.assertFalse(self.puzzle2.answered_by(self.team2))

        # Add a correct guess and check it is marked correct
        guess1 = GuessFactory(for_puzzle=self.puzzle1, by=self.user1, correct=True)
        self.assertTrue(guess1.correct_current)
        self.assertTrue(self.puzzle1.answered_by(self.team1))

        # Add an incorrect guess and check
        guess2 = GuessFactory(for_puzzle=self.puzzle2, by=self.user2, correct=False)
        self.assertTrue(guess2.correct_current)
        self.assertFalse(self.puzzle2.answered_by(self.team2))

        # Alter the answer and check only the first guess is invalidated
        self.answer1.answer = AnswerFactory.build(runtime=self.answer1.runtime).answer
        self.answer1.save()
        guess1.refresh_from_db()
        guess2.refresh_from_db()
        correct = guess1.get_correct_for()
        self.assertTrue(guess1.correct_current)
        self.assertFalse(correct)
        self.assertFalse(self.puzzle1.answered_by(self.team1))

        # Delete the first answer and check
        self.answer1.delete()
        guess1.refresh_from_db()
        guess2.refresh_from_db()
        self.assertTrue(guess2.correct_current)
        self.assertFalse(guess1.get_correct_for())
        self.assertFalse(self.puzzle1.answered_by(self.team1))

        # Add an answer that matches guess 2 and check
        answer = AnswerFactory(for_puzzle=self.puzzle2, runtime=Runtime.STATIC, answer=guess2.guess)
        answer.save()
        guess1.refresh_from_db()
        guess2.refresh_from_db()
        self.assertTrue(guess1.correct_current)
        self.assertFalse(self.puzzle1.answered_by(self.team1))
        self.assertTrue(guess2.get_correct_for())
        self.assertTrue(self.puzzle2.answered_by(self.team2))


class GuessTeamDenormalisationTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.user1 = UserProfileFactory()
        self.user2 = UserProfileFactory()
        self.team1 = TeamFactory(at_event=self.episode.event, members={self.user1})
        self.team2 = TeamFactory(at_event=self.episode.event, members={self.user2})
        self.puzzle1 = PuzzleFactory(episode=self.episode)
        self.puzzle2 = PuzzleFactory(episode=self.episode)

    def test_adding_guess(self):
        guess1 = GuessFactory(for_puzzle=self.puzzle1, by=self.user1, correct=False)
        guess2 = GuessFactory(for_puzzle=self.puzzle2, by=self.user2, correct=False)

        # Check by_team denormalisation.
        self.assertEqual(guess1.by_team, self.team1, "by_team denormalisation consistent with user's team")
        self.assertEqual(guess2.by_team, self.team2, "by_team denormalisation consistent with user's team")

    def test_join_team_updates_guesses(self):
        guess1 = GuessFactory(for_puzzle=self.puzzle1, by=self.user1, correct=False)
        guess2 = GuessFactory(for_puzzle=self.puzzle2, by=self.user2, correct=False)

        # Swap teams and check the guesses update
        self.team1.members.set([])
        self.team2.members.set([self.user1])
        self.team1.save()
        self.team2.save()
        self.team1.members.set([self.user2])
        self.team1.save()

        # Refresh the retrieved Guesses and ensure they are consistent.
        guess1.refresh_from_db()
        guess2.refresh_from_db()
        self.assertEqual(guess1.by_team, self.team2, "by_team denormalisation consistent with user's team")
        self.assertEqual(guess2.by_team, self.team1, "by_team denormalisation consistent with user's team")


class UnlockAnswerTests(EventTestCase):
    def test_unlock_immutable(self):
        unlockanswer = UnlockAnswerFactory()
        new_unlock = UnlockFactory()
        with self.assertRaises(ValueError):
            unlockanswer.unlock = new_unlock
            unlockanswer.save()


class AnnouncementWebsocketTests(AsyncEventTestCase):
    def setUp(self):
        super().setUp()
        self.pz = PuzzleFactory()
        self.ep = self.pz.episode
        self.url = 'ws/hunt/'

    def test_receive_announcement(self):
        profile = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': profile.user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        announcement = AnnouncementFactory(puzzle=None)

        output = self.receive_json(comm, 'Websocket did not send new announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], announcement.message)
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        announcement.message = 'different'
        announcement.save()

        output = self.receive_json(comm, 'Websocket did not send changed announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], 'different')
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        self.run_async(comm.disconnect)()

    def test_receive_delete_announcement(self):
        profile = TeamMemberFactory()
        announcement = AnnouncementFactory(puzzle=None)

        comm = self.get_communicator(websocket_app, self.url, {'user': profile.user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        id = announcement.id
        announcement.delete()

        output = self.receive_json(comm, 'Websocket did not send deleted announcement')
        self.assertEqual(output['type'], 'delete_announcement')
        self.assertEqual(output['content']['announcement_id'], id)

        self.run_async(comm.disconnect)()

    def test_dont_receive_puzzle_specific_announcements(self):
        profile = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': profile.user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        AnnouncementFactory(puzzle=self.pz)

        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect)()


class PuzzleWebsocketTests(AsyncEventTestCase):
    # Missing:
    # disconnect with hints scheduled
    # moving unlock to a different puzzle
    # moving hint to a different puzzle (also not implemented)
    def setUp(self):
        super().setUp()
        self.pz = PuzzleFactory()
        self.ep = self.pz.episode
        self.url = 'ws/hunt/ep/%d/pz/%d/' % (self.ep.get_relative_id(), self.pz.get_relative_id())

    def test_anonymous_access_fails(self):
        comm = WebsocketCommunicator(websocket_app, self.url, headers=self.headers)
        connected, subprotocol = self.run_async(comm.connect)()

        self.assertFalse(connected)

    def test_bad_domain(self):
        user = TeamMemberFactory()
        headers = dict(self.headers)
        headers[b'host'] = b'__BAD__.hunter2.local'
        comm = ScopeOverrideCommunicator(websocket_app, self.url, {'user': user.user}, headers=tuple(headers.items()))
        connected, _ = self.run_async(comm.connect)()

        self.assertFalse(connected)

    def test_bad_requests(self):
        user = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        self.run_async(comm.send_json_to)({'naughty__request!': True})
        output = self.receive_json(comm, 'Websocket did not respond to a bad request')
        self.assertEqual(output['type'], 'error')

        self.run_async(comm.send_json_to)({'type': 'still__bad'})
        output = self.receive_json(comm, 'Websocket did not respond to a bad request')
        self.assertEqual(output['type'], 'error')

        self.run_async(comm.send_json_to)({'type': 'guesses-plz'})
        output = self.receive_json(comm, 'Websocket did not respond to a bad request')
        self.assertEqual(output['type'], 'error')

        self.assertTrue(self.run_async(comm.receive_nothing)())
        self.run_async(comm.disconnect)()

    def test_initial_connection(self):
        ua1 = UnlockAnswerFactory(unlock__puzzle=self.pz)
        UnlockAnswerFactory(unlock__puzzle=self.pz, guess=ua1.guess + '_different')
        h1 = HintFactory(puzzle=self.pz, time=datetime.timedelta(0))
        profile = TeamMemberFactory()
        TeamPuzzleProgressFactory(puzzle=self.pz, team=profile.team_at(self.tenant), start_time=timezone.now())
        g1 = GuessFactory(for_puzzle=self.pz, by=profile)
        g1.given = timezone.now() - datetime.timedelta(days=1)
        g1.save()
        g2 = GuessFactory(for_puzzle=self.pz, guess=ua1.guess, by=profile)
        g2.given = timezone.now()
        g2.save()

        comm = self.get_communicator(websocket_app, self.url, {'user': profile.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)
        self.run_async(comm.send_json_to)({'type': 'guesses-plz', 'from': 'all'})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for old guesses')

        self.assertEqual(output['type'], 'old_guesses')
        self.assertEqual(len(output['content']), 2, 'Websocket did not send the correct number of old guesses')
        self.assertEqual(output['content'][0]['guess'], g1.guess)
        self.assertEqual(output['content'][0]['by'], profile.user.username)
        self.assertEqual(output['content'][1]['guess'], g2.guess)
        self.assertEqual(output['content'][1]['by'], profile.user.username)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Use utcnow() because the JS uses Date.now() which uses UTC - hence the consumer code also uses UTC.
        dt = (datetime.datetime.utcnow() - datetime.timedelta(hours=1))
        # Multiply by 1000 because Date.now() uses ms not seconds
        self.run_async(comm.send_json_to)({'type': 'guesses-plz', 'from': dt.timestamp() * 1000})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for old guesses')
        self.assertTrue(self.run_async(comm.receive_nothing)(), 'Websocket sent guess from before requested cutoff')

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1, 'Websocket did not send the correct number of old guesses')
        self.assertEqual(output['content'][0]['guess'], g2.guess)
        self.assertEqual(output['content'][0]['by'], profile.user.username)

        self.run_async(comm.send_json_to)({'type': 'unlocks-plz'})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for unlocks')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'old_unlock')
        self.assertEqual(output['content']['unlock'], ua1.unlock.text)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.send_json_to)({'type': 'hints-plz', 'from': dt.timestamp() * 1000})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for hints')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], h1.text)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect)()

    def test_same_team_sees_guesses(self):
        team = TeamFactory()
        u1 = UserProfileFactory()
        u2 = UserProfileFactory()
        team.members.add(u1)
        team.members.add(u2)
        team.save()

        comm1 = self.get_communicator(websocket_app, self.url, {'user': u1.user})
        comm2 = self.get_communicator(websocket_app, self.url, {'user': u2.user})

        connected, _ = self.run_async(comm1.connect)()
        self.assertTrue(connected)
        connected, _ = self.run_async(comm2.connect)()
        self.assertTrue(connected)

        g = GuessFactory(for_puzzle=self.pz, correct=False, by=u1)
        g.save()

        output = self.receive_json(comm1, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm1.receive_nothing)())

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['correct'], False)
        self.assertEqual(output['content'][0]['by'], u1.user.username)

        output = self.receive_json(comm2, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm2.receive_nothing)())

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['correct'], False)
        self.assertEqual(output['content'][0]['by'], u1.user.username)

        self.run_async(comm1.disconnect)()
        self.run_async(comm2.disconnect)()

    def test_other_team_sees_no_guesses(self):
        u1 = TeamMemberFactory()
        u2 = TeamMemberFactory()

        comm1 = self.get_communicator(websocket_app, self.url, {'user': u1.user})
        comm2 = self.get_communicator(websocket_app, self.url, {'user': u2.user})

        connected, _ = self.run_async(comm1.connect)()
        self.assertTrue(connected)
        connected, _ = self.run_async(comm2.connect)()
        self.assertTrue(connected)

        g = GuessFactory(for_puzzle=self.pz, correct=False, by=u1)
        g.save()

        self.assertTrue(self.run_async(comm2.receive_nothing)())
        self.run_async(comm1.disconnect)()
        self.run_async(comm2.disconnect)()

    def test_correct_answer_forwards(self):
        user = TeamMemberFactory()
        g = GuessFactory(for_puzzle=self.pz, correct=False, by=user)
        comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        g = GuessFactory(for_puzzle=self.pz, correct=True, by=user)

        self.assertTrue(self.pz.answered_by(user.team_at(self.tenant)))

        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        # We should be notified that we solved the puzzle. Since the episode had just one puzzle,
        # we are now done with that episode and should be redirected back to the episode.
        self.assertEqual(output['type'], 'solved')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['by'], user.user.username)
        self.assertLessEqual(output['content']['time'], 1)
        self.assertEqual(output['content']['redirect'], self.ep.get_absolute_url(), 'Websocket did not redirect to the episode after completing that episode')
        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # We should be notified of the correct guess. Since the episode had just one puzzle,
        # we are now done with that episode and should be redirected back to the episode.
        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['correct'], True)
        self.assertEqual(output['content'][0]['by'], user.user.username)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Request guesses again (as if we had reconnected) and check we get the forwarding message
        self.run_async(comm.send_json_to)({'type': 'guesses-plz', 'from': g.given.astimezone(timezone.utc).timestamp() * 1000})
        output = self.receive_json(comm, 'Websocket did not send notification of having solved the puzzle while disconnected')
        self.assertEqual(output['type'], 'solved')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['by'], user.user.username)
        output = self.receive_json(comm, 'Websocket did nothing in response to requesting guesses again')
        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['by'], user.user.username)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Now add another puzzle. We should be redirected to that puzzle, since it is the
        # unique unfinished puzzle on the episode.
        pz2 = PuzzleFactory(episode=self.ep)
        g.delete()
        g.save()

        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.assertEqual(output['type'], 'solved')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['by'], user.user.username)
        self.assertLessEqual(output['content']['time'], 1)
        self.assertEqual(output['content']['redirect'], pz2.get_absolute_url(),
                         'Websocket did not redirect to the next available puzzle when completing'
                         'one of two puzzles on an episode')

        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        received = output['content'][0]
        self.assertEqual(received['guess'], g.guess)
        self.assertEqual(received['correct'], True)
        self.assertEqual(received['by'], user.user.username)

        self.run_async(comm.disconnect)()

    def test_websocket_receives_unlocks_on_reconnect(self):
        user1 = TeamMemberFactory()
        user2 = TeamMemberFactory()
        ua1 = UnlockAnswerFactory(unlock__puzzle=self.pz, unlock__text='unlock_1', guess='unlock_guess_1')
        ua2 = UnlockAnswerFactory(unlock__puzzle=self.pz, unlock__text='unlock_2', guess='unlock_guess_2')

        comm = self.get_communicator(websocket_app, self.url, {'user': user1.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        GuessFactory(for_puzzle=self.pz, by=user1, guess=ua1.guess)
        self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.receive_json(comm, 'Websocket didn\'t do enough in response to an unlocking guess')
        GuessFactory(for_puzzle=self.pz, by=user2, guess=ua2.guess)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.send_json_to)({'type': 'unlocks-plz'})
        output = self.receive_json(comm, 'Websocket did nothing in response to requesting unlocks again')
        self.assertEqual(output['type'], 'old_unlock')
        self.assertEqual(output['content']['guess'], 'unlock_guess_1')
        self.assertEqual(output['content']['unlock'], 'unlock_1')
        self.assertEqual(output['content']['unlock_uid'], ua1.unlock.compact_id)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect())

    def test_websocket_receives_guess_updates(self):
        user = TeamMemberFactory()
        eve = TeamMemberFactory()
        ua = UnlockAnswerFactory(unlock__puzzle=self.pz, unlock__text='unlock_text', guess='unlock_guess')
        comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
        comm_eve = self.get_communicator(websocket_app, self.url, {'user': eve.user})

        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)
        connected, subprotocol = self.run_async(comm_eve.connect)()
        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())
        self.assertTrue(self.run_async(comm_eve.receive_nothing)())

        g1 = GuessFactory(for_puzzle=self.pz, by=user, guess=ua.guess)
        output1 = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        output2 = self.receive_json(comm, 'Websocket didn\'t do enough in response to a submitted guess')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        try:
            if output1['type'] == 'new_unlock' and output2['type'] == 'new_guesses':
                new_unlock = output1
            elif output2['type'] == 'new_unlock' and output1['type'] == 'new_guesses':
                new_unlock = output2
            else:
                self.fail('Websocket did not receive exactly one each of new_guesses and new_unlock')
        except KeyError:
            self.fail('Websocket did not receive exactly one each of new_guesses and new_unlock')

        self.assertEqual(new_unlock['content']['unlock'], ua.unlock.text)
        self.assertEqual(new_unlock['content']['unlock_uid'], ua.unlock.compact_id)
        self.assertEqual(new_unlock['content']['guess'], g1.guess)

        g2 = GuessFactory(for_puzzle=self.pz, by=user, guess='different_unlock_guess')
        # discard new_guess notification
        self.run_async(comm.receive_json_from)()
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Change the unlockanswer so the other guess validates it, check they are switched over
        ua.guess = g2.guess
        ua.save()
        output1 = self.receive_json(comm, 'Websocket did nothing in response to a changed, unlocked unlockanswer')
        output2 = self.receive_json(comm, 'Websocket did not send the expected two replies in response to unlock guess validation changing')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        try:
            if output1['type'] == 'new_unlock' and output2['type'] == 'delete_unlockguess':
                new_unlock = output1
                delete_unlockguess = output2
            elif output2['type'] == 'new_unlock' and output1['type'] == 'delete_unlockguess':
                new_unlock = output2
                delete_unlockguess = output1
            else:
                self.fail('Websocket did not receive exactly one each of new_guess and delete_unlockguess')
        except KeyError:
            self.fail('Websocket did not receive exactly one each of new_guess and delete_unlockguess')

        self.assertEqual(delete_unlockguess['content']['guess'], g1.guess)
        self.assertEqual(delete_unlockguess['content']['unlock_uid'], ua.unlock.compact_id)
        self.assertEqual(new_unlock['content']['unlock'], ua.unlock.text)
        self.assertEqual(new_unlock['content']['unlock_uid'], ua.unlock.compact_id)
        self.assertEqual(new_unlock['content']['guess'], g2.guess)

        # Change the unlock and check we're told about it
        ua.unlock.text = 'different_unlock_text'
        ua.unlock.save()
        output = self.receive_json(comm, 'Websocket did nothing in response to a changed, unlocked unlock')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'change_unlock')
        self.assertEqual(output['content']['unlock'], ua.unlock.text)
        self.assertEqual(output['content']['unlock_uid'], ua.unlock.compact_id)

        # Delete unlockanswer, check we are told
        ua.delete()
        output = self.receive_json(comm, 'Websocket did nothing in response to a deleted, unlocked unlockanswer')
        self.assertEqual(output['type'], 'delete_unlockguess')
        self.assertEqual(output['content']['guess'], g2.guess)
        self.assertEqual(output['content']['unlock_uid'], ua.unlock.compact_id)

        # Re-add, check we are told
        ua.save()
        output = self.receive_json(comm, 'Websocket did nothing in response to a new, unlocked unlockanswer')
        self.assertEqual(output['type'], 'new_unlock')
        self.assertEqual(output['content']['guess'], g2.guess)
        self.assertEqual(output['content']['unlock'], ua.unlock.text)
        self.assertEqual(output['content']['unlock_uid'], ua.unlock.compact_id)

        # Delete the entire unlock, check we are told
        old_id = ua.unlock.id
        ua.unlock.delete()
        output = self.receive_json(comm, 'Websocket did nothing in response to a deleted, unlocked unlock')

        self.assertEqual(output['type'], 'delete_unlockguess')
        self.assertEqual(output['content']['guess'], 'different_unlock_guess')
        self.assertEqual(output['content']['unlock_uid'], encode_uuid(old_id))

        # Everything is done, check member of another team didn't overhear anything
        self.assertTrue(self.run_async(comm_eve.receive_nothing)(), 'Websocket sent user updates they should not have received')

        self.run_async(comm.disconnect)()
        self.run_async(comm_eve.disconnect)()

    def test_websocket_receives_hints(self):
        # It would be better to mock the asyncio event loop in order to fake advancing time
        # but that's too much effort (and freezegun doesn't support it yet) so just use
        # short delays and hope.
        delay = 0.2

        user = TeamMemberFactory()
        team = user.team_at(self.tenant)
        data = PuzzleData(self.pz, team, user)
        progress = TeamPuzzleProgressFactory(puzzle=self.pz, team=team, start_time=timezone.now())
        data.save()
        hint = HintFactory(puzzle=self.pz, time=datetime.timedelta(seconds=delay))

        comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        # account for delays getting started
        remaining = hint.delay_for_team(team, progress).total_seconds()
        if remaining < 0:
            raise Exception('Websocket hint scheduling test took too long to start up')

        # wait for half the remaining time for output
        self.assertTrue(self.run_async(comm.receive_nothing)(remaining / 2))

        # advance time by all the remaining time
        time.sleep(remaining / 2)
        self.assertTrue(hint.unlocked_by(team, progress))

        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)

        self.run_async(comm.disconnect)()

    def test_websocket_dependent_hints(self):
        delay = 0.3

        user = TeamMemberFactory()
        team = user.team_at(self.tenant)
        progress = TeamPuzzleProgressFactory(puzzle=self.pz, team=team, start_time=timezone.now())
        unlock = UnlockFactory(puzzle=self.pz)
        unlockanswer = unlock.unlockanswer_set.get()
        hint = HintFactory(puzzle=self.pz, time=datetime.timedelta(seconds=delay), start_after=unlock)

        comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        # wait for the remaining time for output
        self.assertTrue(self.run_async(comm.receive_nothing)(delay))

        guess = GuessFactory(for_puzzle=self.pz, by=user, guess=unlockanswer.guess)
        self.receive_json(comm, 'Websocket did not send unlock')
        self.receive_json(comm, 'Websocket did not send guess')
        remaining = hint.delay_for_team(team, progress).total_seconds()
        self.assertFalse(hint.unlocked_by(team, progress))
        self.assertTrue(self.run_async(comm.receive_nothing)(remaining / 2))

        # advance time by all the remaining time
        time.sleep(remaining / 2)
        self.assertTrue(hint.unlocked_by(team, progress))

        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)
        self.assertEqual(output['content']['depends_on_unlock_uid'], unlock.compact_id)

        # alter the unlockanswer to an already-made gss, check hint re-appears
        GuessFactory(for_puzzle=self.pz, by=user, guess='__DIFFERENT__')
        self.receive_json(comm, 'Websocket did not receive new guess')
        unlockanswer.guess = '__DIFFERENT__'
        unlockanswer.save()
        output = self.receive_json(comm, 'Websocket did not delete unlock')
        self.assertEqual(output['type'], 'delete_unlockguess')
        output = self.receive_json(comm, 'Websocket did not resend unlock')
        self.assertEqual(output['type'], 'new_unlock')
        output = self.receive_json(comm, 'Websocket did not resend hint')
        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint_uid'], hint.compact_id)

        # delete the unlockanswer, check for notification
        unlockanswer.delete()

        output = self.receive_json(comm, 'Websocket did not delete unlockanswer')
        self.assertEqual(output['type'], 'delete_unlockguess')

        # guesses are write-only - no notification
        guess.delete()

        # create a new unlockanswer for this unlock
        unlockanswer = UnlockAnswerFactory(unlock=unlock)
        guess = GuessFactory(for_puzzle=self.pz, by=user, guess='__INITIALLY_WRONG__')
        self.receive_json(comm, 'Websocket did not send guess')
        # update the unlockanswer to match the given guess, and check that the dependent
        # hint is scheduled and arrives correctly
        unlockanswer.guess = guess.guess
        unlockanswer.save()
        self.receive_json(comm, 'Websocket did not send unlock')
        self.assertFalse(hint.unlocked_by(team, progress))
        self.assertTrue(self.run_async(comm.receive_nothing)(delay / 2))
        time.sleep(delay / 2)
        self.assertTrue(hint.unlocked_by(team, progress))
        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)
        self.assertEqual(output['content']['depends_on_unlock_uid'], unlock.compact_id)
        self.run_async(comm.disconnect)()

    def test_websocket_receives_hint_updates(self):
        with freezegun.freeze_time() as frozen_datetime:
            user = TeamMemberFactory()
            team = user.team_at(self.tenant)
            progress = TeamPuzzleProgressFactory(puzzle=self.pz, team=team, start_time=timezone.now())

            hint = HintFactory(text='hint_text', puzzle=self.pz, time=datetime.timedelta(seconds=1))
            frozen_datetime.tick(delta=datetime.timedelta(seconds=2))
            self.assertTrue(hint.unlocked_by(team, progress))

            comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
            connected, subprotocol = self.run_async(comm.connect)()
            self.assertTrue(connected)
            self.assertTrue(self.run_async(comm.receive_nothing)())

            hint.text = 'different_hint_text'
            hint.save()

            output = self.receive_json(comm, 'Websocket did not update changed hint text')
            self.assertEqual(output['type'], 'new_hint')
            self.assertEqual(output['content']['hint'], hint.text)
            old_id = output['content']['hint_uid']
            self.assertTrue(self.run_async(comm.receive_nothing)())

            delay = 0.3
            hint.time = datetime.timedelta(seconds=2 + delay)
            hint.save()
            output = self.receive_json(comm, 'Websocket did not remove hint which went into the future')
            self.assertEqual(output['type'], 'delete_hint')
            self.assertEqual(output['content']['hint_uid'], old_id)
            self.assertTrue(self.run_async(comm.receive_nothing)())

            hint.time = datetime.timedelta(seconds=1)
            hint.save()
            output = self.receive_json(comm, 'Websocket did not announce hint which moved into the past')
            self.assertEqual(output['type'], 'new_hint')
            self.assertEqual(output['content']['hint'], hint.text)
            old_id = output['content']['hint_uid']
            self.assertTrue(self.run_async(comm.receive_nothing)())

            hint.delete()
            output = self.receive_json(comm, 'Websocket did not remove hint which was deleted')
            self.assertEqual(output['type'], 'delete_hint')
            self.assertEqual(output['content']['hint_uid'], old_id)
            self.assertTrue(self.run_async(comm.receive_nothing)())

            # Wait for (at most) the delay before the longer hint event would have arrived to check
            # it was correctly cancelled
            self.assertTrue(self.run_async(comm.receive_nothing)(delay))

            self.run_async(comm.disconnect)()

    def test_receive_global_announcement(self):
        profile = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': profile.user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        announcement = AnnouncementFactory(puzzle=None)

        output = self.receive_json(comm, 'Websocket did not send new announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], announcement.message)
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        announcement.message = 'different'
        announcement.save()

        output = self.receive_json(comm, 'Websocket did not send changed announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], 'different')
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        self.run_async(comm.disconnect)()

    def test_receives_puzzle_announcements(self):
        user = TeamMemberFactory()

        comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        # Create an announcement for this puzzle and check we receive updates for it
        ann = AnnouncementFactory(puzzle=self.pz)
        output = self.receive_json(comm, 'Websocket did not send new puzzle announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], ann.id)
        self.assertEqual(output['content']['title'], ann.title)
        self.assertEqual(output['content']['message'], ann.message)
        self.assertEqual(output['content']['variant'], ann.type.variant)

        ann.message = 'different'
        ann.save()

        output = self.receive_json(comm, 'Websocket did not send changed announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], ann.id)
        self.assertEqual(output['content']['title'], ann.title)
        self.assertEqual(output['content']['message'], 'different')
        self.assertEqual(output['content']['variant'], ann.type.variant)

        # Create an announcement for another puzzle and check we don't hear about it
        pz2 = PuzzleFactory()
        ann2 = AnnouncementFactory(puzzle=pz2)
        self.assertTrue(self.run_async(comm.receive_nothing)())
        ann2.message = 'different'
        self.assertTrue(self.run_async(comm.receive_nothing)())
        ann2.delete()
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect)()

    def test_receives_delete_announcement(self):
        profile = TeamMemberFactory()
        announcement = AnnouncementFactory(puzzle=self.pz)

        comm = self.get_communicator(websocket_app, self.url, {'user': profile.user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        id = announcement.id
        announcement.delete()

        output = self.receive_json(comm, 'Websocket did not send deleted announcement')
        self.assertEqual(output['type'], 'delete_announcement')
        self.assertEqual(output['content']['announcement_id'], id)

        self.run_async(comm.disconnect)()


class ContextProcessorTests(AsyncEventTestCase):
    def setUp(self):
        super().setUp()
        self.rf = RequestFactory()
        self.user = UserFactory()
        self.user.save()
        self.client.force_login(self.user)

        self.request = self.rf.get('/')
        self.request.user = self.user
        self.request.tenant = self.tenant

    def test_shows_seat_announcement_if_enabled_and_user_has_no_seat(self):
        AttendanceFactory(user=self.user, event=self.tenant, seat='').save()

        self.tenant.seat_assignments = True

        output = announcements(self.request)

        self.assertEqual(1, len(output['announcements']))
        self.assertEqual('no_seat', output['announcements'][0].id)

    def test_does_not_show_seat_announcement_if_enabled_and_user_has_seat(self):
        AttendanceFactory(user=self.user, event=self.tenant, seat='A1').save()

        self.tenant.seat_assignments = True

        output = announcements(self.request)

        self.assertEqual(0, len(output['announcements']))

    def test_does_not_show_seat_announcement_if_disabled(self):
        AttendanceFactory(user=self.user, event=self.tenant, seat='').save()

        self.tenant.seat_assignments = False

        output = announcements(self.request)

        self.assertEqual(0, len(output['announcements']))

    def test_shows_contact_request_announcement_if_user_has_no_pref(self):
        user = UserFactory(contact=None)
        AttendanceFactory(user=user, event=self.tenant)

        request = self.rf.get('/')
        request.user = user
        request.tenant = self.tenant

        output = announcements(request)

        self.assertIn('no_contact', [a.id for a in output['announcements']], 'Contact request announcement missing from context')

    def test_does_not_show_contact_request_announcement_if_user_has_pref_true(self):
        user = UserFactory(contact=True)
        AttendanceFactory(user=user, event=self.tenant)

        request = self.rf.get('/')
        request.user = user
        request.tenant = self.tenant

        output = announcements(request)

        self.assertNotIn('no_contact', [a.id for a in output['announcements']], 'Unexpected contact request announcement in context')

    def test_does_not_show_contact_request_announcement_if_user_has_pref_false(self):
        user = UserFactory(contact=False)
        AttendanceFactory(user=user, event=self.tenant)

        request = self.rf.get('/')
        request.user = user
        request.tenant = self.tenant

        output = announcements(request)

        self.assertNotIn('no_contact', [a.id for a in output['announcements']], 'Unexpected contact request announcement in context')


class PlayerStatsViewTests(EventTestCase):
    def setUp(self):
        self.url = reverse('player_stats')

    def test_access(self):
        now = timezone.now()
        with freezegun.freeze_time(now) as frozen_datetime:
            users = TeamMemberFactory.create_batch(11, team__role=TeamRole.PLAYER)
            admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
            # Ensure the event has a winning episode containing a puzzle, with a correct guess by a user
            puzzle = PuzzleFactory(episode__event=self.tenant, episode__winning=True)
            for i, user in enumerate(users):
                TeamPuzzleProgressFactory(puzzle=puzzle, team=user.team_at(self.tenant))
                GuessFactory(for_puzzle=puzzle, correct=True, by=user, given=now - datetime.timedelta(minutes=len(users) - i))
            self.tenant.end_date = now + datetime.timedelta(minutes=1)
            self.tenant.save()
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)
            self.client.force_login(admin.user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)
            self.client.force_login(users[-1].user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)
            frozen_datetime.tick(datetime.timedelta(minutes=2))
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.client.logout()
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)

    def test_no_winning_episode(self):
        EpisodeFactory(event=self.tenant, winning=False)
        user = TeamMemberFactory().user
        self.client.force_login(user)
        self.tenant.end_date = timezone.now()
        self.tenant.save()
        self.client.get(self.url)


class ObjectDeletionTests(EventTestCase):
    def test_delete_hint(self):
        hint = HintFactory()
        # Regression test: issue #408
        TeamMemberFactory()

        hint.delete()
