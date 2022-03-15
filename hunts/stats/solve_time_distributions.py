#  Copyright (C) 2022 The Hunter2 Contributors.
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
import json
from math import floor

from django.utils.safestring import mark_safe
from schema import Schema

from hunts.models import Episode, Puzzle
from hunts.stats.abstract import AbstractGenerator
from hunts.stats.puzzle_times import solve_time_tpps_for_puzzle


def _percentile(values, q):
    if not values:
        return 0.0
    N = len(values) - 1
    idx = q * N
    lo = floor(idx)
    h = idx - lo
    a = values[lo]
    if h == 0:
        return a
    else:
        b = values[min(lo + 1, N)]
        return a + h * (b - a)


class SolveDistributionGenerator(AbstractGenerator):
    """
    Generates a distribution of solve times per puzzle
    """
    title = 'Puzzle Solve Time Distributions'
    version = 1

    schema = Schema({
        'episodes': [{
            'id': int,
            'name': str,
            'max_q3': float,
            'puzzles': [{
                'title': str,
                'solve_times': {
                    int: float,
                },
                '90%': float,
            }]
        }]
    })

    def generate(self):
        if self.episode is not None:
            episodes = (self.episode, )
        else:
            episodes = Episode.objects.all()

        output = []

        for episode in episodes:
            puzzles = Puzzle.objects.filter(episode=episode).seal()
            puzzle_solve_times = []
            # The largest Q3 is used for bounds calculation in the frontend
            max_q3 = 0.0
            for puzzle in puzzles:
                tpps = solve_time_tpps_for_puzzle(puzzle)
                solve_times = {
                    tpp.team_id: tpp.solve_time.total_seconds()
                    for tpp in tpps
                }

                vals = list(solve_times.values())
                max_q3 = max(max_q3, _percentile(vals, 0.75))
                # 90th percentile is displayed in the frontend
                ninetieth_percentile = _percentile(vals, 0.9)

                puzzle_solve_times.append({
                    'title': puzzle.title,
                    'solve_times': solve_times,
                    '90%': ninetieth_percentile,
                })

            output.append({
                'id': episode.id,
                'name': episode.name,
                'max_q3': max_q3,
                'puzzles': puzzle_solve_times,
            })
        return {
            'episodes': output
        }

    def render_data(self, data, team=None, user=None):
        team_id = team.id if team is not None else 'undefined'
        data = {
            # Add team ID so that your own team can be highlighted
            'my_team': team_id,
            'episodes': [
                {
                    'id': episode['id'],
                    'name': episode['name'],
                    # calculate an upper limit from the max of the max Q3 calculated above, and this team's solve
                    # time, if it has one
                    'max': max([episode['max_q3']] + [
                        pz['solve_times'].get(team_id, 0)
                        for pz in episode['puzzles']
                    ]),
                    # this data is not used by the template at all so render out to JSON to make the template simpler
                    'puzzles': mark_safe(json.dumps([
                        {
                            'title': puzzle['title'],
                            '90%': puzzle['90%'],
                            'solve_times': puzzle['solve_times'],
                        } for puzzle in episode['puzzles']
                    ])),
                } for episode in data['episodes']
            ],
        }
        return super().render_data(data, team=team, user=user)
