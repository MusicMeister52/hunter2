# Copyright (C) 2022 The Hunter2 Contributors.
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
from os import path

import freezegun
import pytest
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.factories import UserFactory
from events.factories import EventFileFactory, AttendanceFactory
from events.models import Event
from events.test import EventAwareTestCase, EventTestCase, AsyncEventTestCase
from hunter2.factories import FileFactory
from hunter2.models import Configuration
from hunter2.views import DefaultEventView
from teams.factories import TeamMemberFactory
from teams.models import TeamRole
from ..context_processors import announcements
from ..factories import (
    EpisodeFactory,
    GuessFactory,
    PuzzleFactory,
    PuzzleFileFactory,
    SolutionFileFactory,
    TeamPuzzleProgressFactory,
    HintFactory,
)
from ..models import Guess


class ErrorTests(EventTestCase):
    def test_unauthenticated_404(self):
        url = '/does/not/exist'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


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


class TestHomePage:

    @pytest.fixture(scope='class')
    def url(self):
        return reverse('index')

    @pytest.fixture
    def stylish_event(self, event):
        event.script = 'console.log("hello");'
        event.script_file = EventFileFactory(event=event)
        event.style = 'body {width: 1234px;}'
        event.style_file = EventFileFactory(event=event)
        event.save()
        return event

    @pytest.fixture
    def stylish_site(self, db):
        configuration = Configuration.get_solo()
        configuration.script = 'console.log("hello");'
        configuration.script_file = FileFactory()
        configuration.style = 'body {width: 1234px;}'
        configuration.style_file = FileFactory()
        configuration.save()
        return configuration

    def test_load_homepage(self, tenant_client, url):
        response = tenant_client.get(url)
        assert response.status_code == 200

    def test_site_script_and_style(self, stylish_site, tenant_client, url):
        response = tenant_client.get(url)
        content = response.content.decode('utf-8')
        assert stylish_site.script in content
        assert stylish_site.script_file.file.url in content
        assert stylish_site.style in content
        assert stylish_site.style_file.file.url in content

    def test_event_script_and_style(self, stylish_event, tenant_client, url):
        response = tenant_client.get(url)
        content = response.content.decode('utf-8')
        assert stylish_event.script in content
        assert stylish_event.script_file.file.url in content
        assert stylish_event.style in content
        assert stylish_event.style_file.file.url in content


class EventIndexTests(EventTestCase):
    def setUp(self):
        self.url = reverse('event')
        self.player = TeamMemberFactory()
        self.admin = TeamMemberFactory(team__role=TeamRole.ADMIN)

    def test_load_event_index(self):
        self.client.force_login(self.player)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_future_episode_not_visible(self):
        episode = EpisodeFactory(start_date=timezone.now() + datetime.timedelta(hours=1))
        self.client.force_login(self.player)
        response = self.client.get(self.url)
        self.assertNotContains(response, episode.name)

    def test_started_episode_visible(self):
        episode = EpisodeFactory(start_date=timezone.now() - datetime.timedelta(hours=1))
        self.client.force_login(self.player)
        response = self.client.get(self.url)
        self.assertContains(response, episode.name)

    def test_independent_started_episode_visible(self):
        episode1 = EpisodeFactory(start_date=timezone.now() - datetime.timedelta(hours=1))
        episode2 = EpisodeFactory(start_date=timezone.now() - datetime.timedelta(minutes=1))
        self.client.force_login(self.player)
        response = self.client.get(self.url)
        self.assertContains(response, episode1.name)
        self.assertContains(response, episode2.name)

    def test_dependent_locked_episode_not_visible(self):
        episode1 = EpisodeFactory(start_date=timezone.now() - datetime.timedelta(hours=1))
        PuzzleFactory(episode=episode1)
        episode2 = EpisodeFactory(start_date=timezone.now() - datetime.timedelta(minutes=1))
        episode2.add_prequel(episode1)
        self.client.force_login(self.player)
        response = self.client.get(self.url)
        self.assertContains(response, episode1.name)
        self.assertNotContains(response, episode2.name)

    def test_dependent_unlocked_episode_visible(self):
        episode1 = EpisodeFactory(start_date=timezone.now() - datetime.timedelta(hours=1))
        GuessFactory(for_puzzle__episode=episode1, by=self.player, correct=True)
        episode2 = EpisodeFactory(start_date=timezone.now() - datetime.timedelta(minutes=1))
        episode2.add_prequel(episode1)
        self.client.force_login(self.player)
        response = self.client.get(self.url)
        self.assertContains(response, episode1.name)
        self.assertContains(response, episode2.name)


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
        self.client.force_login(self.user)

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
        self.client.force_login(self.user)
        with freezegun.freeze_time() as frozen_datetime:
            self.event.end_date = timezone.now() + datetime.timedelta(seconds=5)
            self.event.save()
            self.assertFalse(Guess.objects.exists())
            response = self.client.post(self.url, {
                'last_updated': '0',
                'answer': '__FIRST__',
            })
            self.assertEqual(response.status_code, 200)
            new_guess = Guess.objects.order_by('given').last()
            self.assertEqual(new_guess.guess, '__FIRST__')
            self.assertEqual(new_guess.late, False)
            frozen_datetime.tick(delta=datetime.timedelta(seconds=10))
            response = self.client.post(self.url, {
                'last_updated': '0',
                'answer': '__SECOND__',
            })
            self.assertEqual(response.status_code, 200)
            new_guess = Guess.objects.order_by('given').last()
            self.assertEqual(new_guess.guess, '__SECOND__')
            self.assertEqual(new_guess.late, True)


class TestHintAcceptance:
    @pytest.fixture
    def puzzle(self, event):
        return PuzzleFactory()

    @pytest.fixture
    def team(self, user, event):
        return user.team_at(event)

    @pytest.fixture
    def user(self, event):
        return TeamMemberFactory()

    @pytest.fixture
    def progress(self, team, puzzle):
        return TeamPuzzleProgressFactory(team=team, puzzle=puzzle, start_time=timezone.now())

    @pytest.fixture
    def hint(self, puzzle):
        return HintFactory(puzzle=puzzle)

    @pytest.fixture
    def client(self, tenant_client):
        # return TenantClient(event)
        return tenant_client

    def test_not_unlocked(self, puzzle, user, team, progress, hint, client):
        client.force_login(user)
        assert not hint.unlocked_by(team, progress)
        url = reverse(
            'accept_hint', kwargs={
                'episode_number': puzzle.episode.get_relative_id(),
                'puzzle_number': puzzle.get_relative_id()
            }
        )
        resp = client.post(url, {'id': hint.compact_id})
        assert resp.status_code == 400

    def test_nonexistent(self, puzzle, user, hint, client):
        client.force_login(user)
        url = reverse(
            'accept_hint', kwargs={
                'episode_number': puzzle.episode.get_relative_id(),
                'puzzle_number': puzzle.get_relative_id()
            }
        )
        resp = client.post(url, {'id': '__NONEXISTENT__'})
        assert resp.status_code == 400

    def test_absent_id(self, puzzle, user, hint, client):
        client.force_login(user)
        url = reverse(
            'accept_hint', kwargs={
                'episode_number': puzzle.episode.get_relative_id(),
                'puzzle_number': puzzle.get_relative_id()
            }
        )
        resp = client.post(url, {})
        assert resp.status_code == 400

    def test_accept_hint(self, puzzle, user, team, progress, hint, client):
        client.force_login(user)
        assert hint not in progress.accepted_hints.all()
        with freezegun.freeze_time() as frozen_datetime:
            frozen_datetime.tick(hint.delay_for_team(team, progress) * 1.01)
            assert hint.unlocked_by(team, progress)
            url = reverse(
                'accept_hint', kwargs={
                    'episode_number': puzzle.episode.get_relative_id(),
                    'puzzle_number': puzzle.get_relative_id()
                }
            )
            resp = client.post(url, {'id': hint.compact_id})
            assert resp.status_code == 200, resp.content
            assert hint in progress.accepted_hints.all()
            assert progress.hint_acceptances.get(hint=hint).accepted_at == timezone.now()


class PuzzleAccessTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory(event=self.tenant, parallel=False)
        self.puzzles = PuzzleFactory.create_batch(3, episode=self.episode)
        self.user = TeamMemberFactory(team__at_event=self.tenant)

    def test_puzzle_view_authorisation(self):
        self.client.force_login(self.user)

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

            # Can load third puzzle, and still callback or answer after event ends
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
            self.assertEqual(resp.status_code, 200)

            # Answer
            resp = self.client.post(
                reverse('answer', kwargs=kwargs),
                {'answer': 'NOT_CORRECT'},  # Deliberately incorrect answer
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(resp.status_code, 200)

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


class FileTests(EventTestCase):
    def setUp(self):
        self.eventfile = EventFileFactory()
        self.user = UserFactory()
        self.client.force_login(self.user)

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
            self.client.force_login(admin)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 404)
            self.client.force_login(users[-1])
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
        user = TeamMemberFactory()
        self.client.force_login(user)
        self.tenant.end_date = timezone.now()
        self.tenant.save()
        self.client.get(self.url)


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
