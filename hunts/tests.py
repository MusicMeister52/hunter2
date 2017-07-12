# vim: set fileencoding=utf-8 :
import datetime

from django.test import TestCase
from django.utils import timezone

from teams.models import Team, UserProfile
from .models import Answer, Guess, Hint, Puzzle, PuzzleData, TeamPuzzleData, Unlock
from .runtimes.registry import RuntimesRegistry as rr


class AnswerValidationTests(TestCase):
    fixtures = ['base', 'test']

    def setUp(self):
        self.puzzle = Puzzle.objects.get()
        self.team = Team.objects.get(pk=1)
        self.data = PuzzleData(self.puzzle, self.team)

    def test_static_answers(self):
        answer = Answer.objects.get(runtime=rr.STATIC)
        guess = Guess.objects.filter(guess='correct', for_puzzle=self.puzzle).get()
        self.assertTrue(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='correctnot', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='incorrect', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='wrong', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))

    def test_regex_answers(self):
        answer = Answer.objects.get(runtime=rr.REGEX)
        guess = Guess.objects.filter(guess='correct', for_puzzle=self.puzzle).get()
        self.assertTrue(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='correctnot', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='incorrect', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='wrong', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))

    def test_lua_answers(self):
        answer = Answer.objects.get(runtime=rr.LUA)
        guess = Guess.objects.filter(guess='correct', for_puzzle=self.puzzle).get()
        self.assertTrue(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='correctnot', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='incorrect', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))
        guess = Guess.objects.filter(guess='wrong', for_puzzle=self.puzzle).get()
        self.assertFalse(answer.validate_guess(guess, self.data))


class PuzzleStartTimeTests(TestCase):
    fixtures = ['base', 'test']

    def test_start_times(self):
        self.assertTrue(self.client.login(username='test', password='hunter2'))
        response = self.client.get('/ep/1/pz/1/', HTTP_HOST='www.testserver')
        self.assertEqual(response.status_code, 200)
        first_time = TeamPuzzleData.objects.get().start_time
        self.assertIsNot(first_time, None)
        response = self.client.get('/ep/1/pz/1/', HTTP_HOST='www.testserver')
        self.assertEqual(response.status_code, 200)
        second_time = TeamPuzzleData.objects.get().start_time
        self.assertEqual(first_time, second_time)


class ClueDisplayTests(TestCase):
    fixtures = ['base', 'test']

    def setUp(self):
        user = UserProfile.objects.get(pk=1)
        self.puzzle = Puzzle.objects.get()
        self.team = Team.objects.get(pk=1)
        self.data = PuzzleData(self.puzzle, self.team, user)

    def test_hint_display(self):
        hint = Hint.objects.get()
        self.assertFalse(hint.unlocked_by(self.team, self.data))
        self.data.tp_data.start_time = timezone.now() + datetime.timedelta(minutes=-5)
        self.assertFalse(hint.unlocked_by(self.team, self.data))
        self.data.tp_data.start_time = timezone.now() + datetime.timedelta(minutes=-10)
        self.assertTrue(hint.unlocked_by(self.team, self.data))

    def test_unlock_display(self):
        unlock = Unlock.objects.get()
        self.assertTrue(unlock.unlocked_by(self.team, self.data))
        fail_team = Team.objects.get(pk=2)
        fail_user = UserProfile.objects.get(pk=2)
        fail_data = PuzzleData(self.puzzle, fail_team, fail_user)
        self.assertFalse(unlock.unlocked_by(fail_team, fail_data))
