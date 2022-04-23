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

import factory
import freezegun
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.factories import UserFactory
from events.test import EventTestCase
from teams.factories import TeamFactory, TeamMemberFactory
from ..factories import (
    AnswerFactory,
    EpisodeFactory,
    GuessFactory,
    HeadstartFactory,
    HintFactory,
    PuzzleFactory,
    TeamPuzzleProgressFactory,
    UnlockAnswerFactory,
    UnlockFactory,
)
from ..models import TeamPuzzleProgress
from ..runtimes import Runtime


class EpisodeBehaviourTests(EventTestCase):
    def test_linear_episodes_are_linear(self):
        linear_episode = EpisodeFactory(parallel=False)
        PuzzleFactory.create_batch(10, episode=linear_episode)
        user = UserFactory()
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
        self.client.force_login(user1)
        unlocked1 = self.client.get(url).context['puzzles']
        self.assertEqual(3, len(unlocked1))
        for puzzle in unlocked1[:2]:
            self.assertTrue(puzzle.solved)
        self.assertFalse(unlocked1[2].solved)

        self.client.force_login(user2)
        unlocked2 = self.client.get(url).context['puzzles']
        self.assertEqual(4, len(unlocked2))
        for puzzle in unlocked2[:3]:
            self.assertTrue(puzzle.solved)
        self.assertFalse(unlocked2[3].solved)

        self.client.force_login(user3)
        unlocked3 = self.client.get(url).context['puzzles']
        self.assertEqual(5, len(unlocked3))
        for puzzle in unlocked3:
            self.assertTrue(puzzle.solved)

    def test_can_see_all_puzzles_after_event_end(self):
        linear_episode = EpisodeFactory(parallel=False)
        num_puzzles = 10
        PuzzleFactory.create_batch(num_puzzles, episode=linear_episode)
        user = TeamMemberFactory(team__at_event=linear_episode.event)
        self.client.force_login(user)
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
            self.client.force_login(user)

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
        user = UserFactory()
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
        user = UserFactory()
        team = TeamFactory(at_event=episode1.event, members=user)
        GuessFactory(for_puzzle=puzzle, by=user, correct=True)
        headstart = HeadstartFactory(episode=episode2, team=team)

        self.assertEqual(episode2.headstart_applied(team), puzzle.headstart_granted + headstart.headstart_adjustment)

    def test_next_linear_puzzle(self):
        linear_episode = EpisodeFactory(parallel=False)
        PuzzleFactory.create_batch(10, episode=linear_episode)
        user = UserFactory()
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
        user = UserFactory()
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
            self.client.force_login(user)
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
            self.client.force_login(user)
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

    def test_episode_prequel_validation(self):
        episode1 = EpisodeFactory()
        episode2 = EpisodeFactory(event=episode1.event, prequels=episode1)
        # Because we intentionally throw exceptions we need to use transaction.atomic() to avoid a TransactionManagementError
        with self.assertRaises(ValidationError), transaction.atomic():
            episode1.add_parent(episode1)
        with self.assertRaises(ValidationError), transaction.atomic():
            episode1.add_parent(episode2)


class ClueTests(EventTestCase):
    def setUp(self):
        self.episode = EpisodeFactory()
        self.user = UserFactory()
        self.puzzle = PuzzleFactory(episode=self.episode)
        self.team = TeamFactory(at_event=self.episode.event, members={self.user})
        self.progress = TeamPuzzleProgressFactory(puzzle=self.puzzle, team=self.team)

    def test_hint_unlocked_by(self):
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

    def test_unlock_unlocked_by(self):
        other_team = TeamFactory(at_event=self.episode.event)

        unlock = UnlockFactory(puzzle=self.puzzle)
        GuessFactory.create(for_puzzle=self.puzzle, by=self.user, guess=unlock.unlockanswer_set.get().guess)

        # Check can only be seen by the correct teams.
        self.assertTrue(unlock.unlocked_by(self.team), "Unlock should be visible not it's been guessed")
        self.assertFalse(unlock.unlocked_by(other_team), "Unlock should not be visible to other team")


class UnlockAnswerTests(EventTestCase):
    def test_unlock_immutable(self):
        unlockanswer = UnlockAnswerFactory()
        new_unlock = UnlockFactory()
        with self.assertRaises(ValueError):
            unlockanswer.unlock = new_unlock
            unlockanswer.save()


class ObjectDeletionTests(EventTestCase):
    def test_delete_hint(self):
        hint = HintFactory()
        # Regression test: issue #408
        TeamMemberFactory()

        hint.delete()


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
