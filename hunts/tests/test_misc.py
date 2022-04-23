# Copyright (C) 2018-2022 The Hunter2 Contributors.
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


from parameterized import parameterized

from accounts.factories import UserFactory
from events.test import EventTestCase
from teams.factories import TeamFactory
from ..factories import (
    AnnouncementFactory,
    AnswerFactory,
    EpisodeFactory,
    GuessFactory,
    HeadstartFactory,
    HintFactory,
    PuzzleFactory,
    PuzzleFileFactory,
    TeamDataFactory,
    TeamPuzzleDataFactory,
    TeamPuzzleProgressFactory,
    UnlockAnswerFactory,
    UnlockFactory,
    UserDataFactory,
    UserPuzzleDataFactory,
)
from ..runtimes import Runtime


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


class CorrectnessCacheTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.event = self.episode.event
        self.user1 = UserFactory()
        self.user2 = UserFactory()
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
        self.user1 = UserFactory()
        self.user2 = UserFactory()
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
