#  Copyright (C) 2021 The Hunter2 Contributors.
#
#  This file is part of Hunter2.
#
#  Hunter2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  Hunter2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License along with Hunter2.  If not, see <http://www.gnu.org/licenses/>.
#
#  This file is part of Hunter2.
#
#  Hunter2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free
#  Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  Hunter2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License along with Hunter2.  If not, see <http://www.gnu.org/licenses/>.
from datetime import timedelta

from django.db.models import F
from schema import And, Schema

from hunts.models import Episode, Puzzle, TeamPuzzleProgress
from hunts.stats.abstract import AbstractGenerator
from teams.models import TeamRole


class PuzzleTimesGenerator(AbstractGenerator):
    """
    Generates a table of solve times per puzzle
    """
    title = 'Puzzle Solve Times'
    version = 1

    schema = Schema([{
        'name': And(str, len),
        'puzzles': [{
            'title': And(str, len),
            'by_team': {
                And(str, len): {
                    'position': int,
                    'solve_time': timedelta,
                }
            },
            'top': {
                (
                    int,
                    And(str, len),
                    timedelta,
                )
            },
        }],
    }])

    def __init__(self, number=10, **kwargs):
        super().__init__(**kwargs)
        self.number = number

    @staticmethod
    def format_solve_time(d):
        hours, r = divmod(d, timedelta(hours=1))
        minutes, r = divmod(r, timedelta(minutes=1))
        seconds, _ = divmod(r, timedelta(seconds=1))
        if hours > 0:
            return f'{hours:d}:{minutes:02d}:{seconds:02d}'
        else:
            return f'{minutes:d}:{seconds:02d}'

    def generate(self):
        if self.episode is not None:
            episodes = (self.episode, )
        else:
            episodes = Episode.objects.all()

        output = []

        for episode in episodes:
            puzzles = Puzzle.objects.filter(episode=episode).seal()
            puzzle_solve_times = []
            for puzzle in puzzles:
                by_team = {}
                by_time = []

                tpps = TeamPuzzleProgress.objects.filter(
                    puzzle=puzzle,
                    start_time__isnull=False,
                    solved_by__isnull=False,
                    team__role=TeamRole.PLAYER,
                ).select_related(
                    'puzzle',
                    'puzzle__episode',
                    'solved_by',
                    'team',
                ).prefetch_related(
                    'puzzle__episode__puzzle_set',
                ).annotate(
                    solve_time=F('solved_by__given') - F('start_time'),
                ).order_by('solve_time').seal()

                for tpp in tpps:
                    if tpp.solve_time < timedelta(0):
                        puzzle_number = tpp.puzzle.get_relative_id()
                        if tpp.puzzle.episode.parallel or puzzle_number == 1:
                            start_time = tpp.puzzle.start_time_for(tpp.team)
                        else:
                            prior_puzzle = tpp.puzzle.episode.puzzle_set.all()[puzzle_number - 1]
                            try:
                                start_time = TeamPuzzleProgress.objects.get(
                                    puzzle=prior_puzzle,
                                    team=tpp.team,
                                    solved_by__isnull=False,
                                ).solved_by.given
                            except TeamPuzzleProgress.DoesNotExist:
                                continue
                        tpp.solve_time = tpp.solved_by.given - start_time

                tpps = sorted(tpps, key=lambda x: x.solve_time)

                for position, tpp in enumerate(tpps):
                    team_name = tpp.team.get_display_name()
                    by_team[team_name] = {
                        'position': position + 1,
                        'solve_time': self.format_solve_time(tpp.solve_time),
                    }
                    by_time.append((position + 1, team_name, self.format_solve_time(tpp.solve_time)))

                puzzle_solve_times.append({
                    'title': puzzle.title,
                    'by_team': by_team,
                    'top': by_time[:self.number],
                })
            output.append({
                'name': episode.name,
                'puzzles': puzzle_solve_times,
            })
        return output

    def render_data(self, data, team=None, user=None):
        data = {
            'episodes': [
                {
                    'name': episode['name'],
                    'puzzles': [
                        {
                            'title': puzzle['title'],
                            'times': self._add_extra(puzzle['by_team'], puzzle['top'], team, 'solve_time'),
                        } for puzzle in episode['puzzles']
                    ],
                } for episode in data
            ],
        }
        return super().render_data(data, team=team, user=user)
