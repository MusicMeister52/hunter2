# Copyright (C) 2021 The Hunter2 Contributors.
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

import json
from datetime import datetime

from django.db.models import F, Min, Q
from django.utils.html import escape
from django.utils.safestring import mark_safe
from schema import And, Schema

from teams.models import TeamRole
from .abstract import AbstractGenerator
from ..models import Episode, TeamPuzzleProgress


class ProgressGenerator(AbstractGenerator):
    """
    Generates a graph showing progress through the hunt

    There is a graph per episode showing the number of puzzles completed against time.
    """
    id = 'progress'
    title = 'Progress Graph'
    version = 2

    template = 'hunts/stats/progress.html'

    schema = Schema({
        'episode_progress': [
            {
                'id': int,
                'name': str,
                'data': {
                    'puzzle_names': [str],
                    'teams': [{
                        'team_id': int,
                        'team_name': And(str, len),
                        'puzzle_times': [{
                            'puzzle': int,
                            'date': datetime,
                        }],
                    }],
                },
            },
        ],
    })

    def __init__(self, number=10, **kwargs):
        super().__init__(**kwargs)
        self.number = number

    def generate(self):
        episodes = [self.episode] if self.episode is not None else Episode.objects.all()

        results = []

        for episode in episodes:
            by_team = {}
            tp_progresses = TeamPuzzleProgress.objects.filter(
                team__role=TeamRole.PLAYER,
                puzzle__episode=episode,
                start_time__isnull=False,
            ).annotate(
                completion_time=Min('puzzle__guess__given', filter=Q(
                    puzzle__guess__by_team=F('team'),
                    puzzle__guess__correct_current=True,
                    puzzle__guess__correct_for__isnull=False,
                ))
            ).order_by(
                'completion_time',
            ).select_related(
                'puzzle',
                'team',
            )

            for tp_progress in tp_progresses:
                team_id = tp_progress.team.id
                # If users changed team they may have a solving guess for a puzzle from before their new team's start time which is wonky
                # Take the minimum of progress time and start time to be the start time
                adjusted_start_time = min(tp_progress.start_time, tp_progress.completion_time) if tp_progress.completion_time else tp_progress.start_time
                if team_id not in by_team:
                    by_team[team_id] = {
                        'team_id': team_id,
                        # We have to escape team names here since they are encoded in JSON which is marked safe later
                        'team_name': escape(tp_progress.team.get_display_name()),
                        'puzzle_times': [{
                            'puzzle_name': '',
                            # Keep the overall start time as a Python datetime to allow comparison below
                            # We'll format them later.
                            'date': adjusted_start_time,
                        }]
                    }
                # In a parallel episode the earliest start time need not have been on the earliest completion time
                elif adjusted_start_time < by_team[team_id]['puzzle_times'][0]['date']:
                    by_team[team_id]['puzzle_times'][0]['date'] = adjusted_start_time

                if tp_progress.completion_time:
                    by_team[team_id]['puzzle_times'].append({
                        'puzzle_name': tp_progress.puzzle.title,
                        'date': tp_progress.completion_time.isoformat(),
                    })

            # Format the start dates now we've finished comparing them
            for team_data in by_team.values():
                team_data['puzzle_times'][0]['date'] = team_data['puzzle_times'][0]['date'].isoformat()

            data = {
                'teams': [team for team in by_team.values() if len(team['puzzle_times']) > 1],
            }

            if not episode.parallel:
                data['puzzle_names'] = [puzzle.title for puzzle in episode.puzzle_set.all()]

            results.append({
                'id': episode.id,
                'name': mark_safe(episode.name),
                'data': mark_safe(json.dumps(data)),
            })

        return {
            'episode_progress': results,
        }
