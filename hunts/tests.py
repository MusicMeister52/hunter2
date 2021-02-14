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
import time

import freezegun
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import transaction
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from parameterized import parameterized
from channels.testing import WebsocketCommunicator

from accounts.factories import UserProfileFactory, UserFactory
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
    UnlockAnswerFactory,
    UnlockFactory,
    UserDataFactory,
    UserPuzzleDataFactory,
)
from .models import PuzzleData, TeamPuzzleData
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


class SiteSetupTest(TestCase):
    def _fixture_setup(self):
        # Ensure there are no Events left over from any EventTestCases before running
        for event in Event.objects.all():
            event.delete(force_drop=True)
            Event.deactivate()
        super()._fixture_setup()

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

        first_time = TeamPuzzleData.objects.get().start_time
        self.assertIsNot(first_time, None, msg='Start time is set on first access to a puzzle')

        response = self.client.get(self.puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200, msg='Puzzle is accessible on absolute url')

        second_time = TeamPuzzleData.objects.get().start_time
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


class EpisodeBehaviourTest(EventTestCase):
    def test_linear_episodes_are_linear(self):
        linear_episode = EpisodeFactory(parallel=False)
        PuzzleFactory.create_batch(10, episode=linear_episode)
        user = UserProfileFactory()
        team = TeamFactory(at_event=linear_episode.event, members=user)

        # TODO: Scramble puzzle order before starting (so they are not in the order they were created).

        # Check we can start and that it is a linear episode.
        self.assertTrue(linear_episode.unlocked_by(team), msg='Episode is unlocked by team')
        self.assertFalse(linear_episode.parallel, msg='Episode is not set as parallel')

        for i in range(1, linear_episode.puzzle_set.count() + 1):
            # Test we have unlocked the question, but not answered it yet.
            self.assertTrue(linear_episode.get_puzzle(i).unlocked_by(team), msg=f'Puzzle[{i}] is unlocked')
            self.assertFalse(linear_episode.get_puzzle(i).answered_by(team), msg=f'Puzzle[{i}] is not answered')

            # Test that we have not unlocked the next puzzle before answering.
            if i < linear_episode.puzzle_set.count():
                self.assertFalse(linear_episode.get_puzzle(i + 1).unlocked_by(team), msg=f'Puzzle[{i + 1}] is not unlocked until previous puzzle answered')

            # Answer the question and assert that it's now answered.
            GuessFactory.create(for_puzzle=linear_episode.get_puzzle(i), by=user, correct=True)
            self.assertTrue(linear_episode.get_puzzle(i).answered_by(team), msg=f'Correct guess has answered puzzle[{i}]')

    def test_can_see_all_parallel_puzzles(self):
        parallel_episode = EpisodeFactory(parallel=True)
        PuzzleFactory.create_batch(5, episode=parallel_episode)
        team = TeamFactory(at_event=parallel_episode.event)

        # Check we can start and that it is a parallel episode.
        self.assertTrue(parallel_episode.unlocked_by(team))
        self.assertTrue(parallel_episode.parallel)

        # Ensure all puzzles in a parallel episode are unlocked.
        for puzzle in parallel_episode.puzzle_set.all():
            self.assertTrue(puzzle.unlocked_by(team), msg='Puzzle unlocked in parallel episode')

    def test_can_see_all_puzzles_after_event_end(self):
        linear_episode = EpisodeFactory(parallel=False)
        num_puzzles = 10
        PuzzleFactory.create_batch(num_puzzles, episode=linear_episode)
        user = UserProfileFactory()
        team = TeamFactory(at_event=linear_episode.event, members=user)

        with freezegun.freeze_time() as frozen_datetime:
            linear_episode.event.end_date = timezone.now()
            frozen_datetime.tick(-60)  # Move a minute before the end of the event
            team_puzzles = linear_episode.unlocked_puzzles(team)
            self.assertEqual(len(team_puzzles), 1, msg='Before the event ends, only the first puzzle is unlocked')
            frozen_datetime.tick(120)  # Move a minute after the end of the event
            team_puzzles = linear_episode.unlocked_puzzles(team)
            self.assertEqual(len(team_puzzles), num_puzzles, msg='After the event ends, all of the puzzles are unlocked')

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

            not_started_parallel_episode = EpisodeFactory(start_date=tz_time + datetime.timedelta(minutes=1), parallel=True)

            not_started_parallel_episode_started_puzzle = PuzzleFactory(
                episode=not_started_parallel_episode,
                start_date=tz_time - datetime.timedelta(minutes=1)
            )
            response = self.client.get(not_started_parallel_episode_started_puzzle.get_absolute_url())
            self.assertEqual(response.status_code, 302)  # Not started episode overrides started puzzle
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
            self.assertEqual(response.status_code, 200)  # Puzzle start time should be ignored for linear episode

    def test_headstarts(self):
        # TODO: Replace with episode sequence factory?
        episode1 = EpisodeFactory()
        episode2 = EpisodeFactory(event=episode1.event, headstart_from=episode1)
        PuzzleFactory.create_batch(10, episode=episode1)
        user = UserProfileFactory()
        team = TeamFactory(at_event=episode1.event, members=user)

        # Check that the headstart granted is the sum of the puzzle headstarts
        headstart = datetime.timedelta()
        self.assertEqual(episode1.headstart_granted(team), datetime.timedelta(minutes=0), "No headstart when puzzles unanswered")

        for i in range(1, episode1.puzzle_set.count() + 1):
            # Start answering puzzles
            GuessFactory.create(for_puzzle=episode1.get_puzzle(i), by=user, correct=True)
            self.assertTrue(episode1.get_puzzle(i).answered_by(team), msg=f'Correct guess has answered puzzle[{i}]')

            # Check headstart summing logic.
            headstart += episode1.get_puzzle(i).headstart_granted
            self.assertEqual(episode1.headstart_granted(team), headstart, "Episode headstart is sum of answered puzzle headstarts")

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
        self.assertTrue(linear_episode.unlocked_by(team), msg='Episode is unlocked by team')
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
        self.assertTrue(parallel_episode.unlocked_by(team), msg='Episode is unlocked by team')
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


class EpisodeSequenceTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.episode1 = EpisodeFactory(event=self.event)
        self.episode2 = EpisodeFactory(event=self.event, prequels=self.episode1)
        self.user = TeamMemberFactory(team__at_event=self.event)

    def test_episode_prequel_validation(self):
        # Because we intentionally throw exceptions we need to use transaction.atomic() to avoid a TransactionManagementError
        with self.assertRaises(ValidationError), transaction.atomic():
            self.episode1.prequels.add(self.episode1)
        with self.assertRaises(ValidationError), transaction.atomic():
            self.episode1.prequels.add(self.episode2)

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
        self.data = PuzzleData(self.puzzle, self.team, self.user)  # Don't actually need to use a factory here.

    def test_hint_display(self):
        hint = HintFactory(puzzle=self.puzzle)

        with freezegun.freeze_time() as frozen_datetime:
            self.data.tp_data.start_time = timezone.now()
            self.assertFalse(hint.unlocked_by(self.team, self.data.tp_data), "Hint not unlocked by team at start")

            frozen_datetime.tick(hint.time / 2)
            self.assertFalse(hint.unlocked_by(self.team, self.data.tp_data), "Hint not unlocked by less than hint time duration.")

            frozen_datetime.tick(hint.time)
            self.assertTrue(hint.unlocked_by(self.team, self.data.tp_data), "Hint unlocked by team after required time elapsed.")

    def test_hint_unlocks_at(self):
        hint = HintFactory(puzzle=self.puzzle, time=datetime.timedelta(seconds=42))

        with freezegun.freeze_time() as frozen_datetime:
            now = timezone.now()
            self.assertEqual(hint.unlocks_at(self.team, self.data.tp_data), None)
            self.data.tp_data.start_time = now
            target = now + datetime.timedelta(seconds=42)

            self.assertEqual(hint.unlocks_at(self.team, self.data.tp_data), target)
            frozen_datetime.tick(datetime.timedelta(seconds=12))
            self.assertEqual(hint.unlocks_at(self.team, self.data.tp_data), target)

        unlock = UnlockFactory(puzzle=self.puzzle)
        hint.start_after = unlock

        with freezegun.freeze_time() as frozen_datetime:
            now = timezone.now()
            self.assertEqual(hint.unlocks_at(self.team, self.data), None)
            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)
            target = now + datetime.timedelta(seconds=42)

            self.assertEqual(hint.unlocks_at(self.team, self.data), target)
            frozen_datetime.tick(datetime.timedelta(seconds=12))
            self.assertEqual(hint.unlocks_at(self.team, self.data), target)

    def test_dependent_hints(self):
        unlock = UnlockFactory(puzzle=self.puzzle)
        hint = HintFactory(puzzle=self.puzzle, start_after=unlock)

        with freezegun.freeze_time() as frozen_datetime:
            self.data.tp_data.start_time = timezone.now()
            self.assertFalse(hint.unlocked_by(self.team, self.data), "Hint unlocked by team at start")

            frozen_datetime.tick(hint.time * 2)
            self.assertFalse(hint.unlocked_by(self.team, self.data),
                             "Hint unlocked by team when dependent unlock not unlocked.")

            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)
            self.assertFalse(hint.unlocked_by(self.team, self.data),
                             "Hint unlocked by team as soon as dependent unlock unlocked")

            frozen_datetime.tick(hint.time / 2)
            self.assertFalse(hint.unlocked_by(self.team, self.data),
                             "Hint unlocked by team before time after dependent unlock was unlocked elapsed")

            frozen_datetime.tick(hint.time)
            self.assertTrue(hint.unlocked_by(self.team, self.data),
                            "Hint not unlocked by team after time after dependent unlock was unlocked elapsed")

            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)
            self.assertTrue(hint.unlocked_by(self.team, self.data),
                            "Hint re-locked by subsequent unlock-validating guess!")

            GuessFactory(for_puzzle=self.puzzle, by=self.user, guess='NOT_CORRECT')
            self.assertTrue(hint.unlocked_by(self.team, self.data),
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
        self.puzzle = PuzzleFactory()
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
        tp_data1 = TeamPuzzleDataFactory(team=team, puzzle=self.puzzle)
        # FIXME: the above does not give tp_data1 a start_time :S
        tp_data1.start_time = timezone.now()
        tp_data1.save()
        TeamPuzzleDataFactory(team=team, puzzle=puzzle2)
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
        guesses = GuessFactory.create_batch(10, for_puzzle=self.puzzle, by=user)
        # The guesses get forced to the current time when created, we have to override afterwards
        for i, guess in enumerate(guesses):
            guess.given = now - datetime.timedelta(minutes=i)
            guess.save()
        tp_data = TeamPuzzleDataFactory(team=team, puzzle=self.puzzle)
        # FIXME: the above does not give tp_data a start_time :S
        tp_data.start_time = timezone.now() - datetime.timedelta(minutes=20)
        tp_data.save()

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
            tp_data = TeamPuzzleDataFactory(team=team, puzzle=self.puzzle)
            tp_data.start_time = timezone.now()
            tp_data.save()
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

            GuessFactory(for_puzzle=self.puzzle, by=member, guess=unlock.unlockanswer_set.all()[0].guess)

            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            response_json = response.json()

            self.assertEqual(len(response_json['puzzles'][0]['clues_visible']), 1)
            self.assertEqual(len(response_json['puzzles'][0]['hints_scheduled']), 1)
            self.assertEqual(response_json['puzzles'][0]['hints_scheduled'][0]['text'], hint.text)

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

    def test_admin_progress_content(self):
        team1 = self.guesses[0].by_team
        team2 = self.guesses[1].by_team

        tp_data1 = TeamPuzzleDataFactory(team=team1, puzzle=self.puzzle)
        # FIXME: the above does not give tp_data1 a start_time :S
        now = timezone.now()
        tp_data1.start_time = now
        tp_data1.save()

        GuessFactory(by=team2.members.all()[0], for_puzzle=self.puzzle, correct=True)
        team3 = TeamPuzzleDataFactory(puzzle=self.puzzle).team

        self.client.force_login(self.admin_user.user)
        url = reverse('admin_progress_content')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        content = response.json()
        self.assertEqual(len(content['puzzles']), 1)
        self.assertEqual(content['puzzles'][0]['title'], self.puzzle.title)

        self.assertEqual(len(content['team_progress']), 7)

        # team1 has opened the puzzle and made an incorrect guess
        team1_data = self._check_team_get_progress(response, team1)
        self.assertEqual(team1_data[0]['puzzle_id'], self.puzzle.id)
        self.assertEqual(team1_data[0]['state'], 'open')
        self.assertEqual(team1_data[0]['guesses'], 1)
        self.assertIsNotNone(team1_data[0]['latest_guess'])
        # Django's JSON encoder truncates the microseconds to milliseconds
        latest_guess = datetime.datetime.fromisoformat(team1_data[0]['latest_guess'].replace('Z', '+00:00'))
        diff = abs(latest_guess - self.guesses[0].given).total_seconds()
        self.assertTrue(diff < 0.001)

        # team2 has opened the puzzle and made a correct guess
        team2_data = self._check_team_get_progress(response, team2)
        self.assertEqual(team2_data[0]['puzzle_id'], self.puzzle.id)
        self.assertEqual(team2_data[0]['state'], 'solved')
        self.assertEqual(team2_data[0]['guesses'], 2)
        self.assertIsNone(team2_data[0]['latest_guess'])

        # team3 has opened the puzzle and made no guesses
        team3_data = self._check_team_get_progress(response, team3)
        self.assertEqual(team3_data[0]['puzzle_id'], self.puzzle.id)
        self.assertEqual(team3_data[0]['state'], 'open')
        self.assertEqual(team3_data[0]['guesses'], 0)
        self.assertIsNone(team3_data[0]['latest_guess'])

    def test_admin_progress_content_hints(self):
        team = self.guesses[0].by_team
        member = self.guesses[0].by
        self.client.force_login(self.admin_user.user)

        url = reverse('admin_progress_content')

        with freezegun.freeze_time() as frozen_datetime:
            tp_data = TeamPuzzleDataFactory(team=team, puzzle=self.puzzle)
            tp_data.start_time = timezone.now()
            tp_data.save()
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

    def test_answered_by_ordering(self):
        puzzle1 = PuzzleFactory(episode=self.episode)

        # Submit two correct answers, 1 an hour after the other
        with freezegun.freeze_time() as frozen_datetime:
            guess1 = GuessFactory(for_puzzle=puzzle1, by=self.user1, correct=True)
            frozen_datetime.tick(datetime.timedelta(hours=1))
            guess2 = GuessFactory(for_puzzle=puzzle1, by=self.user1, correct=True)

            # Fudge another before the first to test ordering.
            frozen_datetime.tick(datetime.timedelta(hours=-2))
            guess3 = GuessFactory(for_puzzle=puzzle1, by=self.user1, correct=True)

            # Ensure the first given answer is reported first
            self.assertEqual(len(puzzle1.answered_by(self.team1)), 3)
            self.assertEqual(puzzle1.answered_by(self.team1)[0], guess3)
            self.assertEqual(puzzle1.answered_by(self.team1)[1], guess1)
            self.assertEqual(puzzle1.answered_by(self.team1)[2], guess2)

    def test_episode_finishing(self):
        # Ensure at least one puzzle in episode.
        puzzles = PuzzleFactory.create_batch(3, episode=self.episode)

        # Check episode has not been completed
        self.assertFalse(self.episode.finished_by(self.team1))

        # Team 1 answer all questions correctly
        for puzzle in puzzles:
            GuessFactory.create(for_puzzle=puzzle, by=self.user1, correct=True)

        # Ensure this team has finished the episode
        self.assertTrue(self.episode.finished_by(self.team1))

    def test_finish_positions(self):
        puzzle1, puzzle2, puzzle3 = PuzzleFactory.create_batch(3, episode=self.episode)

        # Check there are no winners to begin with
        self.assertFalse(self.episode.finished_by(self.team1))
        self.assertFalse(self.episode.finished_by(self.team2))
        self.assertEqual(len(self.episode.finished_positions()), 0)

        # Answer all the questions correctly for both teams with team 1 ahead to begin with then falling behind
        GuessFactory.create(for_puzzle=puzzle1, by=self.user1, correct=True)
        GuessFactory.create(for_puzzle=puzzle2, by=self.user1, correct=True)

        # Check only the first team has finished the first questions
        self.assertEqual(len(puzzle1.finished_teams(self.event)), 1)
        self.assertEqual(puzzle1.finished_teams(self.event)[0], self.team1)
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
        self.assertFalse(guess1.correct_current)
        self.assertTrue(guess2.correct_current)
        correct = guess1.get_correct_for()
        self.assertTrue(guess1.correct_current)
        self.assertFalse(correct)
        self.assertFalse(self.puzzle1.answered_by(self.team1))

        # Update the first guess and check
        guess1.guess = GuessFactory.build(for_puzzle=self.puzzle1, correct=True).guess
        guess1.save()
        self.assertTrue(self.puzzle1.answered_by(self.team1))

        # Delete the first answer and check
        self.answer1.delete()
        guess1.refresh_from_db()
        guess2.refresh_from_db()
        self.assertFalse(guess1.correct_current)
        self.assertTrue(guess2.correct_current)
        self.assertFalse(guess1.get_correct_for())
        self.assertFalse(self.puzzle1.answered_by(self.team1))

        # Add an answer that matches guess 2 and check
        answer = AnswerFactory(for_puzzle=self.puzzle2, runtime=Runtime.STATIC, answer=guess2.guess)
        answer.save()
        guess1.refresh_from_db()
        guess2.refresh_from_db()
        self.assertTrue(guess1.correct_current)
        self.assertFalse(guess2.correct_current)
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
        HintFactory(puzzle=self.pz, time=datetime.timedelta(0))
        profile = TeamMemberFactory()
        data = PuzzleData(self.pz, profile.team_at(self.tenant), profile)
        data.tp_data.start_time = timezone.now()
        data.save()
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

        self.assertEqual(output['type'], 'old_guess')
        self.assertEqual(output['content']['guess'], g1.guess)
        self.assertEqual(output['content']['by'], profile.user.username)

        output = self.receive_json(comm, 'Websocket did not send all old guesses')
        self.assertEqual(output['type'], 'old_guess')
        self.assertEqual(output['content']['guess'], g2.guess)
        self.assertEqual(output['content']['by'], profile.user.username)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Use utcnow() because the JS uses Date.now() which uses UTC - hence the consumer code also uses UTC.
        dt = (datetime.datetime.utcnow() - datetime.timedelta(hours=1))
        # Multiply by 1000 because Date.now() uses ms not seconds
        self.run_async(comm.send_json_to)({'type': 'guesses-plz', 'from': dt.timestamp() * 1000})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for old guesses')
        self.assertTrue(self.run_async(comm.receive_nothing)(), 'Websocket sent guess from before requested cutoff')

        self.assertEqual(output['type'], 'new_guess')
        self.assertEqual(output['content']['guess'], g2.guess)
        self.assertEqual(output['content']['by'], profile.user.username)

        self.run_async(comm.send_json_to)({'type': 'unlocks-plz'})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for unlocks')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'old_unlock')
        self.assertEqual(output['content']['unlock'], ua1.unlock.text)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.send_json_to)({'type': 'hints-plz'})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for hints')
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

        self.assertEqual(output['type'], 'new_guess')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['correct'], False)
        self.assertEqual(output['content']['by'], u1.user.username)

        output = self.receive_json(comm2, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm2.receive_nothing)())

        self.assertEqual(output['type'], 'new_guess')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['correct'], False)
        self.assertEqual(output['content']['by'], u1.user.username)

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
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # We should be notified of the correct guess. Since the episode had just one puzzle,
        # we are now done with that episode and should be redirected back to the episode.
        self.assertEqual(output['type'], 'new_guess')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['correct'], True)
        self.assertEqual(output['content']['by'], user.user.username)
        self.assertEqual(output['content']['redirect'], self.ep.get_absolute_url(), 'Websocket did not redirect to the episode after completing that episode')

        # Now add another puzzle. We should be redirected to that puzzle, since it is the
        # unique unfinished puzzle on the episode.
        pz2 = PuzzleFactory(episode=self.ep)
        g.delete()
        g.save()

        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'new_guess')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['correct'], True)
        self.assertEqual(output['content']['by'], user.user.username)
        self.assertEqual(output['content']['redirect'], pz2.get_absolute_url(),
                         'Websocket did not redirect to the next available puzzle when completing'
                         'one of two puzzles on an episode')

        self.run_async(comm.disconnect)()

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
            if output1['type'] == 'new_unlock' and output2['type'] == 'new_guess':
                new_unlock = output1
            elif output2['type'] == 'new_unlock' and output1['type'] == 'new_guess':
                new_unlock = output2
            else:
                self.fail('Websocket did not receive exactly one each of new_guess and new_unlock')
        except KeyError:
            self.fail('Websocket did not receive exactly one each of new_guess and new_unlock')

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
        output1 = self.receive_json(comm, 'Websocket did nothing in response to a deleted, unlocked unlock')
        output2 = self.receive_json(comm, 'Websocket did nothing in response to a deleted, unlocked unlock')

        # Right now deleting an unlock cascades to the unlockanswers so we get events for both of them.
        # We only actually care about the deleted unlock in this case, but we still check for precise behaviour
        # here since this test ought to be changed if the event no longer cascades.
        try:
            if output1['type'] == 'delete_unlock' and output2['type'] == 'delete_unlockguess':
                delete_unlock = output1
                delete_unlockguess = output2
            elif output2['type'] == 'delete_unlock' and output1['type'] == 'delete_unlockguess':
                delete_unlock = output2
                delete_unlockguess = output1
            else:
                self.fail('Websocket did not receive exactly one each of delete_unlock and delete_unlockguess')
        except KeyError:
            self.fail('Websocket did not receive exactly one each of delete_unlock and delete_unlockguess')

        self.assertEqual(delete_unlock['content']['unlock_uid'], encode_uuid(old_id))

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
        data.tp_data.start_time = timezone.now()
        data.save()
        hint = HintFactory(puzzle=self.pz, time=datetime.timedelta(seconds=delay))

        comm = self.get_communicator(websocket_app, self.url, {'user': user.user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        # account for delays getting started
        remaining = hint.delay_for_team(team, data.tp_data).total_seconds()
        if remaining < 0:
            raise Exception('Websocket hint scheduling test took too long to start up')

        # wait for half the remaining time for output
        self.assertTrue(self.run_async(comm.receive_nothing)(remaining / 2))

        # advance time by all the remaining time
        time.sleep(remaining / 2)
        self.assertTrue(hint.unlocked_by(team, data.tp_data))

        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)

        self.run_async(comm.disconnect)()

    def test_websocket_dependent_hints(self):
        delay = 0.3

        user = TeamMemberFactory()
        team = user.team_at(self.tenant)
        data = PuzzleData(self.pz, team, user)
        data.tp_data.start_time = timezone.now()
        data.save()
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
        remaining = hint.delay_for_team(team, data.tp_data).total_seconds()
        self.assertFalse(hint.unlocked_by(team, data.tp_data))
        self.assertTrue(self.run_async(comm.receive_nothing)(remaining / 2))

        # advance time by all the remaining time
        time.sleep(remaining / 2)
        self.assertTrue(hint.unlocked_by(team, data.tp_data))

        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)
        self.assertEqual(output['content']['depends_on_unlock_uid'], unlock.compact_id)

        # alter the unlockanswer again, check hint re-appears
        guess.guess = '__DIFFERENT_2__'
        guess.save()
        unlockanswer.guess = guess.guess
        unlockanswer.save()
        self.receive_json(comm, 'Websocket did not resend unlock')
        output = self.receive_json(comm, 'Websocket did not resend hint')
        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint_uid'], hint.compact_id)

        # delete the unlockanswer, check for notification
        unlockanswer.delete()

        self.receive_json(comm, 'Websocket did not delete unlockanswer')

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
        self.assertFalse(hint.unlocked_by(team, data.tp_data))
        self.assertTrue(self.run_async(comm.receive_nothing)(delay / 2))
        time.sleep(delay / 2)
        self.assertTrue(hint.unlocked_by(team, data.tp_data))
        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)
        self.assertEqual(output['content']['depends_on_unlock_uid'], unlock.compact_id)
        self.run_async(comm.disconnect)()

    def test_websocket_receives_hint_updates(self):
        with freezegun.freeze_time() as frozen_datetime:
            user = TeamMemberFactory()
            team = user.team_at(self.tenant)
            data = PuzzleData(self.pz, team, user)
            data.tp_data.start_time = timezone.now()
            data.save()

            hint = HintFactory(text='hint_text', puzzle=self.pz, time=datetime.timedelta(seconds=1))
            frozen_datetime.tick(delta=datetime.timedelta(seconds=2))
            self.assertTrue(hint.unlocked_by(team, data.tp_data))

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

            hint.time = datetime.timedelta(seconds=3)
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
        AttendanceFactory(user_info=self.user.info, event=self.tenant, seat='').save()

        self.tenant.seat_assignments = True

        output = announcements(self.request)

        self.assertEqual(1, len(output['announcements']))
        self.assertEqual('no-seat-announcement', output['announcements'][0].id)

    def test_does_not_show_seat_announcement_if_enabled_and_user_has_seat(self):
        AttendanceFactory(user_info=self.user.info, event=self.tenant, seat='A1').save()

        self.tenant.seat_assignments = True

        output = announcements(self.request)

        self.assertEqual(0, len(output['announcements']))

    def test_does_not_show_seat_announcement_if_disabled(self):
        AttendanceFactory(user_info=self.user.info, event=self.tenant, seat='').save()

        self.tenant.seat_assignments = False

        output = announcements(self.request)

        self.assertEqual(0, len(output['announcements']))


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
                TeamPuzzleDataFactory(puzzle=puzzle, team=user.team_at(self.tenant))
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
