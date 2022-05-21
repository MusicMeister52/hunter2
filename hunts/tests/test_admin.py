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

import freezegun
from django.apps import apps
from django.contrib import admin
from django.forms import inlineformset_factory
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.factories import UserFactory
from events.test import EventTestCase
from teams.factories import TeamFactory, TeamMemberFactory
from teams.models import TeamRole
from ..factories import (
    AnswerFactory,
    EpisodeFactory,
    GuessFactory,
    HintFactory,
    PuzzleFactory,
    TeamPuzzleDataFactory,
    TeamPuzzleProgressFactory,
    UnlockAnswerFactory,
    UnlockFactory,
    UserPuzzleDataFactory,
)
from ..forms import AnswerForm
from ..models import EpisodePrequel, Hint, PuzzleFile, SolutionFile, TeamPuzzleData, Unlock, UnlockAnswer, \
    UserPuzzleData, TeamPuzzleProgress, \
    TeamUnlock, Guess, Puzzle, Answer
from ..runtimes import Runtime


class AdminRegistrationTests(TestCase):
    def test_models_registered(self):
        models = apps.get_app_config('hunts').get_models()
        # Models which don't need to be directly registered due to being managed by inlines or being an M2M through model
        inline_models = (EpisodePrequel, Hint, PuzzleFile, SolutionFile, TeamUnlock, Unlock, UnlockAnswer, )
        for model in models:
            if model not in inline_models:
                self.assertIsInstance(admin.site._registry[model], admin.ModelAdmin)


class AdminCreatePageLoadTests(EventTestCase):
    def setUp(self):
        self.user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN, is_staff=True)
        self.client.force_login(self.user)

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
        self.user = TeamMemberFactory(is_staff=True, team__at_event=self.tenant, team__role=TeamRole.ADMIN)
        self.client.force_login(self.user)
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


class AdminExtraAccessTests(EventTestCase):
    def setUp(self):
        self.user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN)
        self.client.force_login(self.user)

    def test_can_view_episode_normally(self):
        self.client.force_login(self.user)
        episode = EpisodeFactory(event=self.tenant)
        response = self.client.get(
            reverse('episode_content', kwargs={'episode_number': episode.get_relative_id()}),
        )
        self.assertEqual(response.status_code, 200)

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


class AdminContentTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory(event=self.tenant)
        self.admin_user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN)
        self.admin_team = self.admin_user.team_at(self.tenant)
        self.player = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.PLAYER)
        self.puzzle = PuzzleFactory(episode=self.episode, start_date=None)
        self.guesses = GuessFactory.create_batch(5, for_puzzle=self.puzzle)
        self.guesses_url = reverse('admin_guesses_list')

    def test_cache_authorisation(self):
        with freezegun.freeze_time():
            self.client.force_login(self.admin_user)
            # add everything to the cache
            response = self.client.get(reverse('admin_guesses'))
            self.assertEqual(response.status_code, 200)
            response = self.client.get(reverse('admin_guesses_list'))
            self.assertEqual(response.status_code, 200)

            response = self.client.get(reverse('admin_stats'))
            self.assertEqual(response.status_code, 200)
            response = self.client.get(reverse('admin_stats_content'))
            self.assertEqual(response.status_code, 200)

            response = self.client.get(reverse('admin_progress'))
            self.assertEqual(response.status_code, 200)
            response = self.client.get(reverse('admin_progress_content'))
            self.assertEqual(response.status_code, 200)

            self.client.force_login(self.player)
            # check that caching does not bypass authentication
            response = self.client.get(reverse('admin_guesses'))
            self.assertEqual(response.status_code, 403)
            response = self.client.get(reverse('admin_guesses_list'))
            self.assertEqual(response.status_code, 403)

            response = self.client.get(reverse('admin_stats'))
            self.assertEqual(response.status_code, 403)
            response = self.client.get(reverse('admin_stats_content'))
            self.assertEqual(response.status_code, 403)

            response = self.client.get(reverse('admin_progress'))
            self.assertEqual(response.status_code, 403)
            response = self.client.get(reverse('admin_progress_content'))
            self.assertEqual(response.status_code, 403)

    def test_can_view_guesses(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_guesses'))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(self.guesses_url)
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_view_guesses(self):
        self.client.force_login(self.player)
        response = self.client.get(reverse('admin_guesses'))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_guesses_list'))
        self.assertEqual(response.status_code, 403)

    def test_can_view_guesses_by_team(self):
        team_id = self.guesses[0].by_team.id
        self.client.force_login(self.admin_user)
        response = self.client.get(f'{self.guesses_url}?team={team_id}')
        self.assertEqual(response.status_code, 200)

    def test_can_view_guesses_by_puzzle(self):
        puzzle_id = self.guesses[0].for_puzzle.id
        self.client.force_login(self.admin_user)
        response = self.client.get(f'{self.guesses_url}?puzzle={puzzle_id}')
        self.assertEqual(response.status_code, 200)

    def test_can_view_guesses_by_episode(self):
        episode_id = self.guesses[0].for_puzzle.episode.id
        self.client.force_login(self.admin_user)
        response = self.client.get(f'{self.guesses_url}?episode={episode_id}')
        self.assertEqual(response.status_code, 200)

    def test_can_view_stats(self):
        stats_url = reverse('admin_stats')
        self.client.force_login(self.admin_user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 200)

    def test_can_view_stats_content(self):
        stats_url = reverse('admin_stats_content')
        self.client.force_login(self.admin_user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 200)

    def test_can_view_stats_content_by_episode(self):
        episode_id = self.guesses[0].for_puzzle.episode.id
        stats_url = reverse('admin_stats_content', kwargs={'episode_id': episode_id})
        self.client.force_login(self.admin_user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_view_stats(self):
        self.client.force_login(self.player)
        response = self.client.get(reverse('admin_stats'))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_stats_content'))
        self.assertEqual(response.status_code, 403)

    def test_non_admin_cannot_view_admin_team(self):
        self.client.force_login(self.player)
        response = self.client.get(reverse('admin_team'))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_team_detail', kwargs={'team_id': self.admin_team.id}))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse('admin_team_detail_content', kwargs={'team_id': self.admin_team.id}))
        self.assertEqual(response.status_code, 403)

    def test_admin_team_detail_not_found(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin_team_detail', kwargs={'team_id': 0}))
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse('admin_team_detail_content', kwargs={'team_id': 0}))
        self.assertEqual(response.status_code, 404)

    def test_can_view_admin_team(self):
        self.client.force_login(self.admin_user)
        url = reverse('admin_team')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_team.get_verbose_name())

    def test_can_view_admin_team_detail(self):
        self.client.force_login(self.admin_user)
        url = reverse('admin_team_detail', kwargs={'team_id': self.admin_team.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_team.get_verbose_name())

    def test_admin_team_detail_content(self):
        team = self.guesses[0].by_team
        puzzle2 = PuzzleFactory()
        GuessFactory(by=team.members.all()[0], for_puzzle=puzzle2, correct=True)

        self.client.force_login(self.admin_user)
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

        self.client.force_login(self.admin_user)
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
        self.client.force_login(self.admin_user)
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
        self.client.force_login(self.admin_user)
        url = reverse('admin_progress')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_non_admin_cannot_view_admin_progress(self):
        self.client.force_login(self.player)
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
        pz2 = PuzzleFactory(episode=self.puzzle.episode)
        with freezegun.freeze_time() as frozen_datetime:
            team1 = self.guesses[0].by_team
            team2 = self.guesses[1].by_team
            tpp1 = TeamPuzzleProgress.objects.get(team=team1, puzzle=self.puzzle)
            tpp1.start_time = timezone.now()
            tpp1.save()
            tpp2 = TeamPuzzleProgress.objects.get(team=team2, puzzle=self.puzzle)
            tpp2.start_time = timezone.now()
            tpp2.save()
            frozen_datetime.tick(datetime.timedelta(seconds=30))
            # Add a team which hasn't guessed at all
            tpp3 = TeamPuzzleProgressFactory(puzzle=self.puzzle)
            tpp3.start_time = timezone.now()
            tpp3.save()
            team3 = tpp3.team
            # Add a team which hasn't even opened a puzzle page
            team4 = TeamFactory()
            frozen_datetime.tick(datetime.timedelta(seconds=30))

            # Add a guess by an admin to confirm they don't appear
            GuessFactory(by=self.admin_user, by_team=self.admin_team, for_puzzle=self.puzzle)
            GuessFactory(by=team2.members.all()[0], for_puzzle=self.puzzle, correct=True)

            self.client.force_login(self.admin_user)
            url = reverse('admin_progress_content')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            content = response.json()
            self.assertEqual(len(content['puzzles']), 2)
            self.assertEqual(content['puzzles'][0]['title'], self.puzzle.title)
            self.assertEqual(content['puzzles'][1]['title'], pz2.title)

            self.assertEqual(len(content['team_progress']), 6)

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
            self.assertEqual(team1_data[1]['puzzle_id'], pz2.id)
            self.assertEqual(team1_data[1]['state'], 'not_opened')

            # team2 has opened the puzzle and made a correct guess
            # move time forwards to verify that time_on is the solve time
            frozen_datetime.tick(datetime.timedelta(minutes=1))
            team2_data = self._check_team_get_progress(response, team2)
            self.assertEqual(team2_data[0]['puzzle_id'], self.puzzle.id)
            self.assertEqual(team2_data[0]['state'], 'solved')
            self.assertEqual(team2_data[0]['guesses'], 2)
            self.assertEqual(team2_data[0]['time_on'], 60)
            self.assertIsNone(team2_data[0]['latest_guess'])
            self.assertEqual(team2_data[1]['puzzle_id'], pz2.id)
            self.assertEqual(team2_data[1]['state'], 'not_opened')

            # team3 has opened the puzzle and made no guesses
            team3_data = self._check_team_get_progress(response, team3)
            self.assertEqual(team3_data[0]['puzzle_id'], self.puzzle.id)
            self.assertEqual(team3_data[0]['state'], 'open')
            self.assertEqual(team3_data[0]['guesses'], 0)
            self.assertEqual(team3_data[0]['time_on'], 30)
            self.assertIsNone(team3_data[0]['latest_guess'])
            self.assertEqual(team3_data[1]['puzzle_id'], pz2.id)
            self.assertEqual(team3_data[1]['state'], 'not_opened')

            # team4 does not appear
            self.assertFalse(any([True for x in response.json()['team_progress'] if x['id'] == team4.id]))

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def test_admin_progress_content_hints(self):
        team = self.guesses[0].by_team
        member = self.guesses[0].by
        self.client.force_login(self.admin_user)

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
        self.client.force_login(self.player)

        url = reverse('reset_progress') + f'?team={self.player.team_at(self.tenant).id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_reset_progress(self):
        self.client.force_login(self.admin_user)

        url = reverse('reset_progress') + f'?team={self.admin_team.id}'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.admin_user.username, msg_prefix='Reset Progress warning page does not contain team member usernames')
        self.assertContains(response, self.admin_team.name, msg_prefix='Reset Progress warning page does not contain team name')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)

    def test_reset_progress_resets_progress(self):
        team = self.player.team_at(self.tenant)

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
        UserPuzzleDataFactory(user=self.player, puzzle=tpp_player.puzzle)

        self.client.force_login(self.admin_user)
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
        self.client.force_login(self.admin_user)
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


class ProgressOrderingTests(EventTestCase):
    def setUp(self):
        self.admin_user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN)
        self.admin_team = self.admin_user.team_at(self.tenant)
        self.puzzle1 = PuzzleFactory(start_date=None)
        self.puzzle2 = PuzzleFactory(episode=self.puzzle1.episode, start_date=None)
        self.player1 = TeamMemberFactory(team__name='1', team__at_event=self.tenant)
        self.player2 = TeamMemberFactory(team__name='2', team__at_event=self.tenant)
        self.player3 = TeamMemberFactory(team__name='3', team__at_event=self.tenant)
        self.tpp1 = TeamPuzzleProgressFactory(team=self.player1.team_at(self.tenant), puzzle=self.puzzle1)
        self.tpp2 = TeamPuzzleProgressFactory(team=self.player2.team_at(self.tenant), puzzle=self.puzzle1)
        self.tpp3 = TeamPuzzleProgressFactory(team=self.player3.team_at(self.tenant), puzzle=self.puzzle1)
        # 2 puzzles
        # [solved 0] [solved 1] [solved 2]
        # [stuck low time] [stuck high time] [stuck cap]
        # [guessed recently] [guessed ages ago]

    @override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
    def get_team_ordering(self):
        self.client.force_login(self.admin_user)
        url = reverse('admin_progress_content')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return [int(p['name']) for p in response.json()['team_progress']]

    def test_admin_progress_content_ordering_different_solved(self):
        GuessFactory(by=self.player1, for_puzzle=self.puzzle1, correct=True)
        GuessFactory(by=self.player1, for_puzzle=self.puzzle2, correct=True)
        GuessFactory(by=self.player3, for_puzzle=self.puzzle1, correct=True)

        GuessFactory(by=self.player2, for_puzzle=self.puzzle1)
        TeamPuzzleProgressFactory(
            team=self.player3.team_at(self.tenant),
            puzzle=self.puzzle2,
            start_time=self.tpp3.start_time - datetime.timedelta(hours=1)
        )

        self.assertEqual(self.get_team_ordering(), [2, 3, 1])

    def test_admin_progress_content_ordering_different_time_stuck(self):
        with freezegun.freeze_time():
            self.tpp1.start_time = timezone.now() - datetime.timedelta(hours=5)
            self.tpp2.start_time = timezone.now() - datetime.timedelta(hours=1)
            self.tpp3.start_time = timezone.now() - datetime.timedelta(hours=3)
            self.tpp1.save()
            self.tpp2.save()
            self.tpp3.save()

            self.assertEqual(self.get_team_ordering(), [1, 3, 2])

    def test_admin_progress_content_ordering_time_stuck_cap(self):
        with freezegun.freeze_time():
            self.tpp1.start_time = timezone.now() - datetime.timedelta(hours=5)
            self.tpp2.start_time = timezone.now() - datetime.timedelta(hours=4)
            self.tpp3.start_time = timezone.now() - datetime.timedelta(hours=6)
            self.tpp1.save()
            self.tpp2.save()
            self.tpp3.save()
            GuessFactory(
                by=self.player1,
                for_puzzle=self.puzzle1,
                given=timezone.now() - datetime.timedelta(minutes=3)
            )
            GuessFactory(
                by=self.player2,
                for_puzzle=self.puzzle1,
                given=timezone.now() - datetime.timedelta(minutes=2)
            )
            GuessFactory(
                by=self.player3,
                for_puzzle=self.puzzle1,
                given=timezone.now() - datetime.timedelta(minutes=1)
            )
            self.assertEqual(self.get_team_ordering(), [3, 2, 1])

    def test_admin_progress_content_ordering_different_recent_guess(self):
        with freezegun.freeze_time():
            self.tpp1.start_time = timezone.now() - datetime.timedelta(hours=1)
            self.tpp2.start_time = timezone.now() - datetime.timedelta(hours=1)
            self.tpp3.start_time = timezone.now() - datetime.timedelta(hours=1)
            self.tpp1.save()
            self.tpp2.save()
            self.tpp3.save()
            GuessFactory(
                by=self.player1,
                for_puzzle=self.puzzle1,
                given=timezone.now() - datetime.timedelta(minutes=2)
            )
            GuessFactory(
                by=self.player2,
                for_puzzle=self.puzzle1,
                given=timezone.now() - datetime.timedelta(minutes=1)
            )
            GuessFactory(
                by=self.player3,
                for_puzzle=self.puzzle1,
                given=timezone.now() - datetime.timedelta(minutes=3)
            )
            self.assertEqual(self.get_team_ordering(), [2, 1, 3])

    def test_admin_progress_content_ordering_by_id(self):
        with freezegun.freeze_time():
            self.tpp1.start_time = timezone.now() - datetime.timedelta(hours=1)
            self.tpp2.start_time = timezone.now() - datetime.timedelta(hours=1)
            self.tpp3.start_time = timezone.now() - datetime.timedelta(hours=1)
            self.tpp1.save()
            self.tpp2.save()
            self.tpp3.save()

            self.assertEqual(self.get_team_ordering(), [1, 2, 3])


class StatsTests(EventTestCase):
    def setUp(self):
        self.admin_user = TeamMemberFactory(team__at_event=self.tenant, team__role=TeamRole.ADMIN)

    def test_no_episodes(self):
        stats_url = reverse('admin_stats_content')
        self.client.force_login(self.admin_user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 404)

    def test_filter_invalid_episode(self):
        episode = EpisodeFactory(event=self.tenant)
        # The next sequantial ID ought to not exist
        stats_url = reverse('admin_stats_content', kwargs={'episode_id': episode.id + 1})
        self.client.force_login(self.admin_user)
        response = self.client.get(stats_url)
        self.assertEqual(response.status_code, 404)


class AnswerFormValidationTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.event = self.episode.event
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.team1 = TeamFactory(at_event=self.event, members={self.user1})
        self.team2 = TeamFactory(at_event=self.event, members={self.user2})

        # Generate a puzzle.
        self.puzzle1 = PuzzleFactory(episode=self.episode, answer_set__runtime=Runtime.STATIC)

        # Get the answer to the puzzle to provide it as guesses
        self.answer1 = self.puzzle1.answer_set.get()

        # Set the options on the answer, we want no case_handling, so that only
        # one of the guesses is correct.
        self.answer1.options = {'case_handling': 'none'}
        self.answer1.save()

        # Give each team an answer to the puzzle.
        guess1 = GuessFactory(for_puzzle=self.puzzle1, by=self.user1, guess=str(self.answer1))
        guess2 = GuessFactory(for_puzzle=self.puzzle1, by=self.user2, guess=str(self.answer1).upper())
        guess1.save()
        guess2.save()

        # Only 1 team should be finished.
        self.assertTrue(len(self.puzzle1.finished_teams()) == 1)

        # We need a formset to test deletion
        self.AnswerFormSet = inlineformset_factory(Puzzle, Answer, form=AnswerForm, can_delete=True)

    # Test that changing nothing, does nothing.
    def test_changing_nothing(self):
        formset = self.AnswerFormSet(instance=self.puzzle1, data={
            'answer_set-TOTAL_FORMS': 1,
            'answer_set-INITIAL_FORMS': 1,
            'answer_set-0-id': self.answer1.id,
            'answer_set-0-answer': self.answer1.answer,
            'answer_set-0-runtime': self.answer1.runtime,
            'answer_set-0-options': self.answer1.options,
            'answer_set-0-alter_progress': '',
            'answer_set-0-DELETE': '',
        })
        self.assertTrue(formset.is_valid())

    # Test changing answer options
    def test_changing_option_no_progress_change(self):
        # Change the options specifically to case-handling none. This should
        # be fine as it should not advance any team.
        formset = self.AnswerFormSet(instance=self.puzzle1, data={
            'answer_set-TOTAL_FORMS': 1,
            'answer_set-INITIAL_FORMS': 1,
            'answer_set-0-id': self.answer1.id,
            'answer_set-0-answer': self.answer1.answer,
            'answer_set-0-runtime': self.answer1.runtime,
            'answer_set-0-options': {'case_handling': 'none'},
            'answer_set-0-alter_progress': '',
            'answer_set-0-DELETE': '',
        })
        self.assertTrue(formset.is_valid())

    def test_changing_option_with_progress_change(self):
        # Change the options specifically to case-handling lower, should
        # cause an error because this will advance team2.
        formset = self.AnswerFormSet(instance=self.puzzle1, data={
            'answer_set-TOTAL_FORMS': 1,
            'answer_set-INITIAL_FORMS': 1,
            'answer_set-0-id': self.answer1.id,
            'answer_set-0-answer': self.answer1.answer,
            'answer_set-0-runtime': self.answer1.runtime,
            'answer_set-0-options': {'case_handling': 'lower'},
            'answer_set-0-alter_progress': '',
            'answer_set-0-DELETE': '',
        })
        self.assertFalse(formset.is_valid())

    def test_changing_option_with_progress_change_accepted(self):
        # Change the options specifically to case-handling lower
        # will advance team2 but we have set alter_progress to True
        formset = self.AnswerFormSet(instance=self.puzzle1, data={
            'answer_set-TOTAL_FORMS': 1,
            'answer_set-INITIAL_FORMS': 1,
            'answer_set-0-id': self.answer1.id,
            'answer_set-0-answer': self.answer1.answer,
            'answer_set-0-runtime': self.answer1.runtime,
            'answer_set-0-options': {'case_handling': 'lower'},
            'answer_set-0-alter_progress': 'on',
            'answer_set-0-DELETE': '',
        })
        self.assertTrue(formset.is_valid())

    # Test deleting an answer
    def test_deleting_answers(self):
        # Deleting should cause an error because it will stop team1 having
        # a valid answer
        formset = self.AnswerFormSet(instance=self.puzzle1, data={
            'answer_set-TOTAL_FORMS': 1,
            'answer_set-INITIAL_FORMS': 1,
            'answer_set-0-id': self.answer1.id,
            'answer_set-0-answer': self.answer1.answer,
            'answer_set-0-runtime': self.answer1.runtime,
            'answer_set-0-options': self.answer1.options,
            'answer_set-0-alter_progress': '',
            'answer_set-0-DELETE': 'on',
        })
        self.assertFalse(formset.is_valid())

    def test_deleting_answers_with_alter_progress(self):
        # Deleting an answer with alter_progress True should be fine.

        formset = self.AnswerFormSet(instance=self.puzzle1, data={
            'answer_set-TOTAL_FORMS': 1,
            'answer_set-INITIAL_FORMS': 1,
            'answer_set-0-id': self.answer1.id,
            'answer_set-0-answer': self.answer1.answer,
            'answer_set-0-runtime': self.answer1.runtime,
            'answer_set-0-options': self.answer1.options,
            'answer_set-0-alter_progress': 'on',
            'answer_set-0-DELETE': 'on',
        })
        self.assertTrue(formset.is_valid())
