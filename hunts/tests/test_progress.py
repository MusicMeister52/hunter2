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
from django.urls import reverse
from django.utils import timezone

from accounts.factories import UserFactory
from events.test import EventTestCase
from teams.factories import TeamFactory, TeamMemberFactory
from .. import utils
from ..factories import (
    AnswerFactory,
    EpisodeFactory,
    GuessFactory,
    PuzzleFactory,
    UnlockAnswerFactory,
)
from ..models import TeamPuzzleProgress, \
    TeamUnlock, Answer, \
    Guess
from ..runtimes import Runtime


class EpisodeSequenceTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.episode1 = EpisodeFactory(event=self.event)
        self.episode2 = EpisodeFactory(event=self.event, prequels=self.episode1)
        self.user = TeamMemberFactory(team__at_event=self.event)

    def test_episode_unlocking(self):
        puzzle = PuzzleFactory(episode=self.episode1)

        self.client.force_login(self.user)

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


class EventWinningTests(EventTestCase):
    fixtures = ["teams_test"]

    def setUp(self):
        self.ep1 = EpisodeFactory(winning=True)
        self.ep2 = EpisodeFactory(winning=False)
        self.user1 = UserFactory()
        self.user2 = UserFactory()
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

    def test_start_times_recorded_correctly(self):
        self.puzzle = PuzzleFactory()
        self.episode = self.puzzle.episode
        self.event = self.episode.event
        self.user = TeamMemberFactory(team__at_event=self.event)

        self.client.force_login(self.user)

        response = self.client.get(self.puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200, msg='Puzzle is accessible on absolute url')

        first_time = TeamPuzzleProgress.objects.get().start_time
        self.assertIsNot(first_time, None, msg='Start time is set on first access to a puzzle')

        response = self.client.get(self.puzzle.get_absolute_url())
        self.assertEqual(response.status_code, 200, msg='Puzzle is accessible on absolute url')

        second_time = TeamPuzzleProgress.objects.get().start_time
        self.assertEqual(first_time, second_time, msg='Start time does not alter on subsequent access')


class ProgressionMethodTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.event = self.episode.event
        self.user1 = UserFactory()
        self.user2 = UserFactory()
        self.team1 = TeamFactory(at_event=self.event, members={self.user1})
        self.team2 = TeamFactory(at_event=self.event, members={self.user2})

    def test_episode_available(self):
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

    def test_finished_positions(self):
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

    def test_first_correct_guesses(self):
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
