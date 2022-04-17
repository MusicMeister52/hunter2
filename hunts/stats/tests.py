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

from django.db.models.signals import post_save
from django.test import SimpleTestCase
from django.utils import timezone
from faker import Faker
import pytest
from schema import Schema


from accounts.factories import UserFactory
from events.models import Event
from teams.factories import TeamFactory, TeamMemberFactory
from teams.models import TeamRole
from . import PuzzleTimesGenerator, SolveDistributionGenerator
from ..factories import GuessFactory, PuzzleFactory, EpisodeFactory, TeamPuzzleProgressFactory
from .abstract import AbstractGenerator
from .leaders import LeadersGenerator
from .top_guesses import TopGuessesGenerator
from .totals import TotalsGenerator
from ..models import TeamPuzzleProgress, Answer


@pytest.fixture
def late_guesser(event):
    player = TeamMemberFactory(team__role=TeamRole.PLAYER)

    # every time an answer is created, guess correctly on the corresponding puzzle and flag it late.
    # this can't be registered to puzzle creation, because when it's created it won't have any answers.
    def create_and_guess(sender, instance, created, **kwargs):
        if created:
            GuessFactory(by=player, for_puzzle=instance.for_puzzle, late=True, correct=True)

    post_save.connect(create_and_guess, sender=Answer, dispatch_uid=player.id)

    yield

    post_save.disconnect(sender=Answer, dispatch_uid=player.id)


class MockStat(AbstractGenerator):
    id = 'mock'
    title = 'Mock Statistic'
    version = 2

    schema = Schema(dict)

    def generate(self, episode=None):
        # This generator always returns different data, so we can test cache hit/miss
        fake = Faker()
        return fake.pydict()


class StatCacheTests(SimpleTestCase):
    def setUp(self):
        # We don't want to depend on a database, but we need an event object with an ID
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
        self.stat.version = 3
        self.assertNotEqual(data, self.stat.data())


class TestLeaders:
    def test_event_leaders(self, event):
        puzzle = PuzzleFactory(episode__winning=True)
        players = TeamMemberFactory.create_batch(4, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish the puzzle in order 1-4
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=4 - i)) for i, player in enumerate(players)]
        # Player 4 also guessed wrong
        GuessFactory(by=players[3], for_puzzle=puzzle, correct=False, given=now - timedelta(minutes=5))

        data = LeadersGenerator(event=event, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        assert len(data['top']) == 3
        for i, player in enumerate(players[:3]):
            assert data['top'][i] == (i + 1, player.team_at(event).get_display_name(), guesses[i].given)
        # The fourth team appears correctly in the indexed data
        team = players[3].team_at(event).id
        assert team in data['by_team']
        assert data['by_team'][team]['position'] == 4
        assert data['by_team'][team]['finish_time'] == guesses[3].given

    def test_episode_leaders(self, event):
        puzzle1 = PuzzleFactory(episode__winning=False)
        puzzle2 = PuzzleFactory(episode__winning=True, episode__prequels=puzzle1.episode)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish puzzle 1 in order 1-3
        guesses = [GuessFactory(by=player, for_puzzle=puzzle1, correct=True, given=now - timedelta(minutes=6 - i)) for i, player in enumerate(players)]
        # Players finish puzzle 2 in order 3-1
        for i, player in enumerate(reversed(players)):
            GuessFactory(by=player, for_puzzle=puzzle2, correct=True, given=now - timedelta(minutes=3 - i))

        data = LeadersGenerator(event=event, episode=puzzle1.episode, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        assert len(data['top']) == 3
        for i, player in enumerate(players):
            assert data['top'][i] == (i + 1, player.team_at(event).get_display_name(), guesses[i].given)

    def test_leaders_not_enough_players(self, event):
        puzzle = PuzzleFactory(episode__winning=True)
        players = TeamMemberFactory.create_batch(2, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # Players finish the puzzle in order 1-2
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=2-i)) for i, player in enumerate(players)]

        data = LeadersGenerator(event=event, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 2 entries, in order, with the correct times
        assert len(data['top']) == 2
        for i, player in enumerate(players):
            assert data['top'][i] == (i + 1, player.team_at(event).get_display_name(), guesses[i].given)

    def test_leaders_no_winning_episode(self, event):
        puzzle = PuzzleFactory(episode__winning=False)
        player = TeamMemberFactory(team__role=TeamRole.PLAYER)
        GuessFactory(by=player, for_puzzle=puzzle, correct=True)

        with pytest.raises(ValueError):
            LeadersGenerator(event=event).generate()

    def test_admin_excluded(self, event):
        puzzle = PuzzleFactory(episode__winning=True)
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # The admin solved the winning puzzle long ago
        GuessFactory(by=admin, for_puzzle=puzzle, correct=True, given=now - timedelta(days=7))
        # Players finish the puzzle in order 1-3
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=3-i)) for i, player in enumerate(players)]

        data = LeadersGenerator(event=event, number=3).generate()
        LeadersGenerator.schema.is_valid(data)

        # "Top" has 3 entries
        assert len(data['top']) == 3
        for i, player in enumerate(players):
            assert data['top'][i] == (i + 1, player.team_at(event).get_display_name(), guesses[i].given)
        # Admin team is not in the indexed data
        assert admin.team_at(event).id not in data['by_team']


class TestTopGuesses:
    def test_event_top_guesses(self, event):
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

        data = TopGuessesGenerator(event=event, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        # Player 2 and 4 are on the same team, so they win by team
        assert len(data['top_teams']) == 3
        assert data['top_teams'][0] == (1, team2.get_display_name(), 6)
        assert data['top_teams'][1] == (2, players[0].team_at(event).get_display_name(), 5)
        assert data['top_teams'][2] == (3, players[2].team_at(event).get_display_name(), 3)
        assert len(data['top_users']) == 3
        for i, player in enumerate(players[:3]):
            assert data['top_users'][i] == (i + 1, player.get_display_name(), 5 - i)
        # The fourth and fifth users, and fourth team appear correctly in the indexed data
        team5 = players[4].team_at(event).id
        assert team5 in data['by_team']
        assert data['by_team'][team5]['position'] == 4
        assert data['by_team'][team5]['guess_count'] == 1
        for i, player in enumerate(players[3:]):
            assert player.id in data['by_user']
            assert data['by_user'][player.id]['position'] == i + 4
            assert data['by_user'][player.id]['guess_count'] == 2 - i

    def test_episode_top_guesses(self, event):
        puzzles = PuzzleFactory.create_batch(2)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        # Create guesses such that players won episode 1 in order 1-3 but episode 2 in order 3-1
        for i, player in enumerate(players):
            GuessFactory.create_batch(3 - i, by=player, for_puzzle=puzzles[0])
            GuessFactory.create_batch(i * 2 + 1, by=player, for_puzzle=puzzles[1])

        data = TopGuessesGenerator(event=event, episode=puzzles[0].episode, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order
        assert len(data['top_users']) == 3
        for i, player in enumerate(players):
            assert data['top_users'][i] == (i + 1, player.get_display_name(), 3 - i)

    def test_top_guesses_not_enough_players(self, event):
        puzzle = PuzzleFactory()
        players = UserFactory.create_batch(2)
        team = TeamFactory(members=players, role=TeamRole.PLAYER)
        for i, player in enumerate(players):
            GuessFactory.create_batch(2 - i, by=player, for_puzzle=puzzle)

        data = TopGuessesGenerator(event=event, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        # "Top Users" has 2 entries, in order
        assert len(data['top_users']) == 2
        for i, player in enumerate(players):
            assert data['top_users'][i] == (i + 1, player.get_display_name(), 2 - i)
        # "Top Teams" has 1 entry
        assert len(data['top_teams']) == 1
        assert data['top_teams'][0] == (1, team.get_display_name(), 3)

    def test_admin_excluded(self, event):
        puzzle = PuzzleFactory()
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        GuessFactory.create_batch(4, by=admin, for_puzzle=puzzle)
        for i, player in enumerate(players):
            GuessFactory.create_batch(3 - i, by=player, for_puzzle=puzzle)

        data = TopGuessesGenerator(event=event, number=3).generate()
        TopGuessesGenerator.schema.is_valid(data)

        assert len(data['top_teams']) == 3
        for i, player in enumerate(players):
            assert data['top_teams'][i] == (i + 1, player.team_at(event).get_display_name(), 3 - i)
        assert len(data['top_users']) == 3
        for i, player in enumerate(players):
            assert data['top_users'][i] == (i + 1, player.get_display_name(), 3 - i)
        # Admin team/user is not in the indexed data
        assert admin.team_at(event).id not in data['by_team']
        assert admin.id not in data['by_user']

    def test_render_extra_data(self, event):
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

        render = TopGuessesGenerator(event=event, number=3).render_data(data, team=team, user=user)

        assert 'Team 4' in render
        assert 'User 4' in render

    def test_render_no_duplicate(self, event):
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

        render = TopGuessesGenerator(event=event, number=3).render_data(data, team=team, user=user)

        assert 1 == render.count('Team 3')
        assert 1 == render.count('User 3')


@pytest.mark.usefixtures("late_guesser")
class TestTotals:
    def test_event_totals(self, event):
        puzzle = PuzzleFactory(episode__winning=True)
        puzzle2 = PuzzleFactory(episode__winning=True)
        puzzle3 = PuzzleFactory(episode__winning=False)
        players = TeamMemberFactory.create_batch(3, team__role=TeamRole.PLAYER)
        players += UserFactory.create_batch(2)
        TeamFactory(members=(players[3], players[4]))
        for i, player in enumerate(players[1:]):  # Player 0 is not active
            GuessFactory(by=player, for_puzzle=puzzle, correct=False)
        for player in players[2:]:  # Player 1 did not get the puzzle right
            GuessFactory(by=player, for_puzzle=puzzle, correct=True)
        GuessFactory(by=players[3], for_puzzle=puzzle2, correct=True)
        GuessFactory(by=players[4], for_puzzle=puzzle3, correct=True)

        data = TotalsGenerator(event=event).generate()
        TotalsGenerator.schema.is_valid(data)

        assert data['active_players'] == 4
        assert data['active_teams'] == 3
        assert data['correct_teams'] == 2
        assert data['finished_teams'] == 1
        assert data['puzzles_solved'] == 4
        assert data['guess_count'] == 9

    def test_episode_totals(self, event):
        episode = EpisodeFactory(winning=False)
        puzzles = PuzzleFactory.create_batch(2, episode=episode)
        irrelevant_puzzle = PuzzleFactory()
        players = TeamMemberFactory.create_batch(2, team__role=TeamRole.PLAYER)

        GuessFactory(by=players[0], for_puzzle=puzzles[0], correct=True)
        GuessFactory(by=players[0], for_puzzle=puzzles[1], correct=True)
        GuessFactory(by=players[1], for_puzzle=puzzles[1], correct=True)
        GuessFactory(by=players[1], for_puzzle=irrelevant_puzzle, correct=True)

        data = TotalsGenerator(event=event, episode=puzzles[0].episode).generate()
        TotalsGenerator.schema.is_valid(data)

        assert data['active_players'] == 2
        assert data['active_teams'] == 2
        assert data['correct_teams'] == 2
        assert data['finished_teams'] == 1
        assert data['puzzles_solved'] == 3
        assert data['guess_count'] == 3

    def test_admin_excluded(self, event):
        puzzle = PuzzleFactory()
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        player = TeamMemberFactory(team__role=TeamRole.PLAYER)
        GuessFactory(by=admin, for_puzzle=puzzle, correct=True)
        GuessFactory(by=player, for_puzzle=puzzle, correct=True)

        data = TotalsGenerator(event=event).generate()
        TotalsGenerator.schema.is_valid(data)

        assert data['active_players'] == 1
        assert data['active_teams'] == 1
        assert data['correct_teams'] == 1
        assert data['finished_teams'] == 0  # There is no winning episode
        assert data['puzzles_solved'] == 1
        assert data['guess_count'] == 1


@pytest.mark.usefixtures("late_guesser")
class TestPuzzleTimes:
    def test_event_puzzle_times(self, event):
        puzzle = PuzzleFactory(episode__winning=True)
        players = TeamMemberFactory.create_batch(4, team__role=TeamRole.PLAYER)
        now = timezone.now()
        # All teams started at the same time
        for player in players:
            TeamPuzzleProgressFactory(team=player.team_at(event), puzzle=puzzle, start_time=now - timedelta(hours=1))
        # Players finish the puzzle in order 1-4
        guesses = [GuessFactory(by=player, for_puzzle=puzzle, correct=True, given=now - timedelta(minutes=4 - i)) for i, player in enumerate(players)]
        # Player 4 also guessed wrong
        GuessFactory(by=players[3], for_puzzle=puzzle, correct=False, given=now - timedelta(minutes=5))

        data = PuzzleTimesGenerator(event=event, number=3).generate()
        PuzzleTimesGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        assert len(data[0]['puzzles'][0]['top']) == 3
        for i, player in enumerate(players[:3]):
            team = player.teams.get()
            tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle, team=team)
            assert data[0]['puzzles'][0]['top'][i] == (
                i + 1,
                team.get_display_name(),
                PuzzleTimesGenerator.format_solve_time(guesses[i].given - tpp.start_time)
            )
        # The fourth team appears correctly in the indexed data
        team = players[3].teams.get()
        tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle, team=team)
        assert team.id in data[0]['puzzles'][0]['by_team']
        assert data[0]['puzzles'][0]['by_team'][team.id]['position'] == 4
        assert data[0]['puzzles'][0]['by_team'][team.id]['solve_time'] == PuzzleTimesGenerator.format_solve_time(guesses[3].given - tpp.start_time)

    def test_episode_puzzle_times(self, event):
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

        data = PuzzleTimesGenerator(event=event, number=3).generate()
        PuzzleTimesGenerator.schema.is_valid(data)

        # "Top" has 3 entries, in order, with the correct times
        assert len(data[1]['puzzles'][0]['top']) == 3
        for i, player in enumerate(players[:3]):
            team = player.teams.get()
            tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle1, team=team)
            assert data[1]['puzzles'][0]['top'][i] == (
                i + 1, team.get_display_name(), PuzzleTimesGenerator.format_solve_time(guesses[i].given - tpp.start_time)
            )
        # The fourth team appears correctly in the indexed data
        team = players[3].teams.get()
        tpp = TeamPuzzleProgress.objects.get(puzzle=puzzle1, team=team)
        assert team.id in data[1]['puzzles'][0]['by_team']
        assert data[1]['puzzles'][0]['by_team'][team.id]['position'] == 4
        assert data[1]['puzzles'][0]['by_team'][team.id]['solve_time'] == PuzzleTimesGenerator.format_solve_time(guesses[3].given - tpp.start_time)

    def test_admin_excluded(self, event):
        puzzle = PuzzleFactory()
        admin = TeamMemberFactory(team__role=TeamRole.ADMIN)
        player = TeamMemberFactory(team__role=TeamRole.PLAYER)
        GuessFactory(by=admin, for_puzzle=puzzle, correct=True)
        GuessFactory(by=player, for_puzzle=puzzle, correct=True)

        data = PuzzleTimesGenerator(event=event).generate()
        PuzzleTimesGenerator.schema.is_valid(data)

        assert len(data[0]['puzzles'][0]['top']) == 1
        assert admin.teams.get().get_display_name() not in data[0]['puzzles'][0]['by_team']


@pytest.mark.usefixtures("late_guesser")
class TestSolveDistribution:
    def test_episode_puzzle_times(self, event):
        puzzle1 = PuzzleFactory(episode__winning=False)
        puzzle2 = PuzzleFactory(episode__winning=True, episode__prequels=puzzle1.episode)
        players = TeamMemberFactory.create_batch(4, team__role=TeamRole.PLAYER)
        teams = [player.team_at(event) for player in players]
        now = timezone.now()
        for i, (player, team) in enumerate(zip(players, teams)):
            TeamPuzzleProgressFactory(puzzle=puzzle1, team=team, start_time=now - timedelta(minutes=5))
            TeamPuzzleProgressFactory(puzzle=puzzle2, team=team, start_time=now - timedelta(minutes=5))
            GuessFactory(by=player, for_puzzle=puzzle1, correct=True, given=now - timedelta(minutes=4 - i))
            GuessFactory(by=player, for_puzzle=puzzle2, correct=True, given=now - timedelta(minutes=3))

        data = SolveDistributionGenerator(event=event).generate()
        assert SolveDistributionGenerator.schema.is_valid(data)
        ep1 = 0 if data['episodes'][0]['id'] == puzzle1.episode.id else 1
        ep2 = 1 - ep1
        assert data['episodes'][ep1]['max_q3'] >= 180.0
        assert data['episodes'][ep1]['max_q3'] <= 240.0
        assert len(data['episodes'][ep1]['puzzles']) == 1
        assert (
            data['episodes'][ep1]['puzzles'][0]['solve_times'] ==
            {team.id: 60 * (i+1) for i, team in enumerate(teams)}
        )
        assert data['episodes'][ep1]['puzzles'][0]['90%'] >= data['episodes'][ep1]['max_q3']
        assert data['episodes'][ep1]['puzzles'][0]['90%'] <= 240.0
        assert data['episodes'][ep2]['max_q3'] == 120.0
        assert len(data['episodes'][ep2]['puzzles']) == 1
        assert (
            data['episodes'][ep2]['puzzles'][0]['solve_times'] ==
            {team.id: 60 * 2 for team in teams}
        )
