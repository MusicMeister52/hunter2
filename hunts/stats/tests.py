# Copyright (C) 2020 The Hunter2 Contributors.
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

from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone
from faker import Faker
from schema import Schema

from accounts.factories import UserFactory
from events.models import Event
from events.test import EventTestCase
from teams.factories import TeamFactory, TeamMemberFactory
from teams.models import TeamRole
from . import PuzzleTimesGenerator
from ..factories import GuessFactory, PuzzleFactory
from .abstract import AbstractGenerator
from .leaders import LeadersGenerator
from .top_guesses import TopGuessesGenerator
from .totals import TotalsGenerator
from ..models import TeamPuzzleProgress


class MockStat(AbstractGenerator):
    id = 'mock'
    title = 'Mock Statistic'
    version = 1

    schema = Schema(dict)

    def generate(self, episode=None):
        # This generator always returns different data so we can test cache hit/miss
        fake = Faker()
        return fake.pydict()


class StatCacheTests(SimpleTestCase):
    def setUp(self):
        # We don't want to depend on a database but we need an event object with an ID
        self.event = Event(id=1)
        self.stat = MockStat(self.event)

    def test_cache_hit(self):
        data = self.stat.data()
        self.assertEqual(data, self.stat.data())

    def test_class_change_cache_miss(self):
        class OtherStat(MockStat):
            pass
        other_stat = OtherStat(self.event)
        data = self.stat.data()
        self.assertNotEqual(data, other_stat.data())

    def test_version_change_cache_miss(self):
        data = self.stat.data()
        self.stat.version = 2
        self.assertNotEqual(data, self.stat.data())


class LeadersTests(EventTestCase):
    def test_event_leaders(self):
        puzzle = PuzzleFactory(episode__winning=True)
        players = TeamMemberFactory.create_batch(4, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish the puzzle in order 1-4
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=4 - i)) for i, player in enumerate(players)]
        # Player 4 also guessed wrong
        GuessFactory(by=players[3], for_puzzle=puzzle, correct=False, given=now - timedelta(minutes=5))

        data = LeadersGenerator(event=self.tenant, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        self.assertEqual(len(data['top']), 3)
        for i, player in enumerate(players[:3]):
            self.assertEqual(data['top'][i], (i + 1, player.team_at(self.tenant).get_display_name(), guesses[i].given))
        # The fourth team appears correctly in the indexed data
        team = players[3].team_at(self.tenant).id
        self.assertIn(team, data['by_team'])
        self.assertEqual(data['by_team'][team]['position'], 4)
        self.assertEqual(data['by_team'][team]['finish_time'], guesses[3].given)

    def test_episode_leaders(self):
        puzzle1 = PuzzleFactory(episode__winning=False)
        puzzle2 = PuzzleFactory(episode__winning=True, episode__prequels=puzzle1.episode)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish puzzle 1 in order 1-3
        guesses = [GuessFactory(by=player, for_puzzle=puzzle1, correct=True, given=now - timedelta(minutes=6 - i)) for i, player in enumerate(players)]
        # Players finish puzzle 2 in order 3-1
        for i, player in enumerate(reversed(players)):
            GuessFactory(by=player, for_puzzle=puzzle2, correct=True, given=now - timedelta(minutes=3 - i))

        data = LeadersGenerator(event=self.tenant, episode=puzzle1.episode, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        self.assertEqual(len(data['top']), 3)
        for i, player in enumerate(players):
            self.assertEqual(data['top'][i], (i + 1, player.team_at(self.tenant).get_display_name(), guesses[i].given))

    def test_leaders_not_enough_players(self):
        puzzle = PuzzleFactory(episode__winning=True)
        players = TeamMemberFactory.create_batch(2, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish the puzzle in order 1-2
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=2-i)) for i, player in enumerate(players)]

        data = LeadersGenerator(event=self.tenant, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 2 entries, in order, with the correct times
        self.assertEqual(len(data['top']), 2)
        for i, player in enumerate(players):
            self.assertEqual(data['top'][i], (i + 1, player.team_at(self.tenant).get_display_name(), guesses[i].given))

    def test_leaders_no_winning_episode(self):
        puzzle = PuzzleFactory(episode__winning=False)
        player = TeamMemberFactory(team__role=TeamRole.PLAYER)
        GuessFactory(by=player, for_puzzle=puzzle, correct=True)

        with self.assertRaises(ValueError):
            LeadersGenerator(event=self.tenant).generate()

    def test_admin_excluded(self):
        puzzle = PuzzleFactory(episode__winning=True)
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # The admin solved the winning puzzle long ago
        GuessFactory(by=admin, for_puzzle=puzzle, correct=True, given=now - timedelta(days=7))
        # Players finish the puzzle in order 1-3
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=3-i)) for i, player in enumerate(players)]

        data = LeadersGenerator(event=self.tenant, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 3 entries
        self.assertEqual(len(data['top']), 3)
        for i, player in enumerate(players):
            self.assertEqual(data['top'][i], (i + 1, player.team_at(self.tenant).get_display_name(), guesses[i].given))
        # Admin team is not in the indexed data
        self.assertNotIn(admin.team_at(self.tenant).id, data['by_team'])


class TopGuessesTests(EventTestCase):
    def test_event_top_guesses(self):
        puzzle = PuzzleFactory()
        players = (  # Not using create_batch because we want some of the middle ones to not be on teams
            TeamMemberFactory(team__role=TeamRole.PLAYER),
            UserFactory(),
            TeamMemberFactory(team__role=TeamRole.PLAYER),
            UserFactory(),
            TeamMemberFactory(team__role=TeamRole.PLAYER),
        )
        team2 = TeamFactory(members=(players[1], players[3]))
        for i, player in enumerate(players):
            GuessFactory.create_batch(5 - i, by=player, for_puzzle=puzzle)

        data = TopGuessesGenerator(event=self.tenant, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        # Player 2 and 4 are on the same team, so they win by team
        self.assertEqual(len(data['top_teams']), 3)
        self.assertEqual(data['top_teams'][0], (1, team2.get_display_name(), 6))
        self.assertEqual(data['top_teams'][1], (2, players[0].team_at(self.tenant).get_display_name(), 5))
        self.assertEqual(data['top_teams'][2], (3, players[2].team_at(self.tenant).get_display_name(), 3))
        self.assertEqual(len(data['top_users']), 3)
        for i, player in enumerate(players[:3]):
            self.assertEqual(data['top_users'][i], (i + 1, player.get_display_name(), 5 - i))
        # The fourth and fifth users, and fourth team appear correctly in the indexed data
        team5 = players[4].team_at(self.tenant).id
        self.assertIn(team5, data['by_team'])
        self.assertEqual(data['by_team'][team5]['position'], 4)
        self.assertEqual(data['by_team'][team5]['guess_count'], 1)
        for i, player in enumerate(players[3:]):
            self.assertIn(player.id, data['by_user'])
            self.assertEqual(data['by_user'][player.id]['position'], i + 4)
            self.assertEqual(data['by_user'][player.id]['guess_count'], 2 - i)

    def test_episode_top_guesses(self):
        puzzles = PuzzleFactory.create_batch(2)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        # Create guesses such that players won episode 1 in order 1-3 but episode 2 in order 3-1
        for i, player in enumerate(players):
            GuessFactory.create_batch(3 - i, by=player, for_puzzle=puzzles[0])
            GuessFactory.create_batch(i * 2 + 1, by=player, for_puzzle=puzzles[1])

        data = TopGuessesGenerator(event=self.tenant, episode=puzzles[0].episode, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order
        self.assertEqual(len(data['top_users']), 3)
        for i, player in enumerate(players):
            self.assertEqual(data['top_users'][i], (i + 1, player.get_display_name(), 3 - i))

    def test_top_guesses_not_enough_players(self):
        puzzle = PuzzleFactory()
        players = UserFactory.create_batch(2)
        team = TeamFactory(members=players, role=TeamRole.PLAYER)
        for i, player in enumerate(players):
            GuessFactory.create_batch(2 - i, by=player, for_puzzle=puzzle)

        data = TopGuessesGenerator(event=self.tenant, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        # "Top Users" has 2 entries, in order
        self.assertEqual(len(data['top_users']), 2)
        for i, player in enumerate(players):
            self.assertEqual(data['top_users'][i], (i + 1, player.get_display_name(), 2 - i))
        # "Top Teams" has 1 entry
        self.assertEqual(len(data['top_teams']), 1)
        self.assertEqual(data['top_teams'][0], (1, team.get_display_name(), 3))

    def test_admin_excluded(self):
        puzzle = PuzzleFactory()
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        GuessFactory.create_batch(4, by=admin, for_puzzle=puzzle)
        for i, player in enumerate(players):
            GuessFactory.create_batch(3 - i, by=player, for_puzzle=puzzle)

        data = TopGuessesGenerator(event=self.tenant, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        self.assertEqual(len(data['top_teams']), 3)
        for i, player in enumerate(players):
            self.assertEqual(data['top_teams'][i], (i + 1, player.team_at(self.tenant).get_display_name(), 3 - i))
        self.assertEqual(len(data['top_users']), 3)
        for i, player in enumerate(players):
            self.assertEqual(data['top_users'][i], (i + 1, player.get_display_name(), 3 - i))
        # Admin team/user is not in the indexed data
        self.assertNotIn(admin.team_at(self.tenant).id, data['by_team'])
        self.assertNotIn(admin.id, data['by_user'])

    def test_render_extra_data(self):
        team = TeamFactory.build(name='Team 4')
        team.id = 4
        user = UserFactory.build(username='User 4')
        user.id = 4
        data = {
            'by_team': {
                1: {'position': 1, 'guess_count': 4},
                2: {'position': 2, 'guess_count': 3},
                3: {'position': 3, 'guess_count': 2},
                4: {'position': 4, 'guess_count': 1},
            },
            'by_user': {
                1: {'position': 1, 'guess_count': 4},
                2: {'position': 2, 'guess_count': 3},
                3: {'position': 3, 'guess_count': 2},
                4: {'position': 4, 'guess_count': 1},
            },
            'top_teams': [
                (1, 'Team 1', 4),
                (2, 'Team 2', 3),
                (3, 'Team 3', 2),
            ],
            'top_users': [
                (1, 'User 1', 4),
                (2, 'User 2', 3),
                (3, 'User 3', 2),
            ],
        }

        render = TopGuessesGenerator(event=self.tenant, number=3).render_data(data, team=team, user=user)

        self.assertIn('Team 4', render)
        self.assertIn('User 4', render)

    def test_render_no_duplicate(self):
        team = TeamFactory.build(name='Team 3')
        team.id = 3
        user = UserFactory.build(username='User 3')
        user.id = 3

        data = {
            'by_team': {
                1: {'position': 1, 'guess_count': 1},
                2: {'position': 2, 'guess_count': 1},
                3: {'position': 3, 'guess_count': 1},
                4: {'position': 4, 'guess_count': 1},
            },
            'by_user': {
                1: {'position': 1, 'guess_count': 4},
                2: {'position': 2, 'guess_count': 3},
                3: {'position': 3, 'guess_count': 2},
                4: {'position': 4, 'guess_count': 1},
            },
            'top_teams': [
                (1, 'Team 1', 4),
                (2, 'Team 2', 3),
                (3, 'Team 3', 2),
            ],
            'top_users': [
                (1, 'User 1', 4),
                (2, 'User 2', 3),
                (3, 'User 3', 2),
            ],
        }

        render = TopGuessesGenerator(event=self.tenant, number=3).render_data(data, team=team, user=user)

        self.assertEqual(1, render.count('Team 3'))
        self.assertEqual(1, render.count('User 3'))


class TotalsTests(EventTestCase):
    def test_event_totals(self):
        puzzle = PuzzleFactory()
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        players += UserFactory.create_batch(2)
        TeamFactory(members=(players[3], players[4]))
        for i, player in enumerate(players[1:]):  # Player 0 is not active
            GuessFactory(by=player, for_puzzle=puzzle, correct=False)
        for player in players[2:]:  # Player 1 did not get the puzzle right
            GuessFactory(by=player, for_puzzle=puzzle, correct=True)

        data = TotalsGenerator(event=self.tenant).generate()
        TotalsGenerator.schema.is_valid(data)

        self.assertEqual(data['active_players'], 4)
        self.assertEqual(data['active_teams'], 3)
        self.assertEqual(data['correct_teams'], 2)
        self.assertEqual(data['puzzles_solved'], 2)
        self.assertEqual(data['guess_count'], 7)

    def test_episode_totals(self):
        puzzles = PuzzleFactory.create_batch(2)
        players = TeamMemberFactory.create_batch(2, team__role=TeamRole.PLAYER)

        GuessFactory(by=players[0], for_puzzle=puzzles[0], correct=True)
        GuessFactory(by=players[0], for_puzzle=puzzles[1], correct=True)
        GuessFactory(by=players[1], for_puzzle=puzzles[1], correct=True)

        data = TotalsGenerator(event=self.tenant, episode=puzzles[0].episode).generate()
        TotalsGenerator.schema.is_valid(data)

        self.assertEqual(data['active_players'], 1)
        self.assertEqual(data['active_teams'], 1)
        self.assertEqual(data['correct_teams'], 1)
        self.assertEqual(data['puzzles_solved'], 1)
        self.assertEqual(data['guess_count'], 1)

    def test_admin_excluded(self):
        puzzle = PuzzleFactory()
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        player = TeamMemberFactory(team__role=TeamRole.PLAYER)
        GuessFactory(by=admin, for_puzzle=puzzle, correct=True)
        GuessFactory(by=player, for_puzzle=puzzle, correct=True)

        data = TotalsGenerator(event=self.tenant).generate()
        TotalsGenerator.schema.is_valid(data)

        self.assertEqual(data['active_players'], 1)
        self.assertEqual(data['active_teams'], 1)
        self.assertEqual(data['correct_teams'], 1)
        self.assertEqual(data['puzzles_solved'], 1)
        self.assertEqual(data['guess_count'], 1)


class PuzzleTimesTests(EventTestCase):
    def test_event_puzzle_times(self):
        puzzle = PuzzleFactory(episode__winning=True)
        players = TeamMemberFactory.create_batch(4, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish the puzzle in order 1-4
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=4 - i)) for i, player in enumerate(players)]
        # Player 4 also guessed wrong
        GuessFactory(by=players[3], for_puzzle=puzzle, correct=False, given=now - timedelta(minutes=5))

        data = PuzzleTimesGenerator(event=self.tenant, number=3).generate()
        PuzzleTimesGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        self.assertEqual(len(data[0]['puzzles'][0]['top']), 3)
        for i, player in enumerate(players[:3]):
            team = player.team_at(self.tenant)
            tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle, team=team)
            self.assertEqual(
                data[0]['puzzles'][0]['top'][i],
                (i + 1, team.get_display_name(), PuzzleTimesGenerator.format_solve_time(guesses[i].given - tpp.start_time)),
            )
        # The fourth team appears correctly in the indexed data
        team = players[3].team_at(self.tenant)
        tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle, team=team)
        self.assertIn(team.id, data[0]['puzzles'][0]['by_team'])
        self.assertEqual(data[0]['puzzles'][0]['by_team'][team.id]['position'], 4)
        self.assertEqual(data[0]['puzzles'][0]['by_team'][team.id]['solve_time'], PuzzleTimesGenerator.format_solve_time(guesses[3].given - tpp.start_time))

    def test_episode_puzzle_times(self):
        puzzle1 = PuzzleFactory(episode__winning=False)
        puzzle2 = PuzzleFactory(episode__winning=True, episode__prequels=puzzle1.episode)
        players = TeamMemberFactory.create_batch(4, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish the puzzle in order 1-4
        for i, player in enumerate(players):
            GuessFactory(by=player, for_puzzle=puzzle1, correct=True, given=now - timedelta(minutes=4 - i))
        # Players finish the puzzle in order 4-1
        guesses = [
            GuessFactory(by=player, for_puzzle=puzzle2, correct=True, given=now - timedelta(minutes=4 - i))
            for i, player in enumerate(reversed(players))
        ]

        data = PuzzleTimesGenerator(event=self.tenant, number=3).generate()
        PuzzleTimesGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        self.assertEqual(len(data[1]['puzzles'][0]['top']), 3)
        for i, player in enumerate(players[:3]):
            team = player.team_at(self.tenant)
            tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle1, team=team)
            self.assertEqual(
                data[1]['puzzles'][0]['top'][i],
                (i + 1, team.get_display_name(), PuzzleTimesGenerator.format_solve_time(guesses[i].given - tpp.start_time)),
            )
        # The fourth team appears correctly in the indexed data
        team = players[3].team_at(self.tenant)
        tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle1, team=team)
        self.assertIn(team.id, data[1]['puzzles'][0]['by_team'])
        self.assertEqual(data[1]['puzzles'][0]['by_team'][team.id]['position'], 4)
        self.assertEqual(data[1]['puzzles'][0]['by_team'][team.id]['solve_time'], PuzzleTimesGenerator.format_solve_time(guesses[3].given - tpp.start_time))

    def test_admin_excluded(self):
        puzzle = PuzzleFactory()
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        player = TeamMemberFactory(team__role=TeamRole.PLAYER)
        GuessFactory(by=admin, for_puzzle=puzzle, correct=True)
        GuessFactory(by=player, for_puzzle=puzzle, correct=True)

        data = PuzzleTimesGenerator(event=self.tenant).generate()
        PuzzleTimesGenerator.schema.is_valid(data)

        self.assertEqual(len(data[0]['puzzles'][0]['top']), 1)
        self.assertNotIn(admin.team_at(self.tenant).get_display_name(), data[0]['puzzles'][0]['by_team'])
