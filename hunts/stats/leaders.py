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

from datetime import datetime

from schema import And, Schema

from .abstract import AbstractGenerator
from ..models import Episode


class LeadersGenerator(AbstractGenerator):
    """
    Generates a table of the hunt leaders

    Leaders are defined as the first teams to finished all puzzles in all winning episodes.
    """
    title = 'Leaderboard'
    version = 1

    schema = Schema({
        'by_team': {
            And(str, len): {
                'finish_time': datetime,
            },
        },
        'top': [
            (
                int,
                And(str, len),
                datetime,
            ),
        ],
    })

    def __init__(self, number=10, **kwargs):
        super().__init__(**kwargs)
        self.number = number

    def generate(self):
        if self.episode is not None:
            episodes = [self.episode]
        else:
            episodes = Episode.objects.filter(winning=True)
            # If any "winning" episodes have anything in their sequel graph which are also "winning" then discount them since completion times for the sequels
            # must be higher
            redundant = [e.id for e in episodes if len([s for s in e.all_sequels() if s.winning])]
            episodes = episodes.exclude(pk__in=redundant)
            if episodes.count() == 0:
                raise ValueError("Event has no winning episodes")

        # We have at least one episode, copy the first episode's finish times
        team_times = {team: time for team, time in episodes[0].finished_times()}
        # Iterate remaining episodes to find people who finished later than the existing time or did not finish
        for episode in episodes[1:]:
            old_times = team_times
            team_times = {}
            for team, time in episode.finished_times():
                if team in old_times:
                    team_times[team] = max(old_times[team], time)

        sorted_team_times = list(sorted(team_times.items(), key=lambda x: x[1]))
        top = [(position, team.get_display_name(), time) for position, (team, time) in enumerate(sorted_team_times, start=1)][:self.number]
        by_team = {
            team.id: {
                'position': position,
                'finish_time': time,
            } for position, (team, time) in enumerate(sorted_team_times, start=1)
        }

        return {
            'by_team': by_team,
            'top': top,
        }

    def render_data(self, data, team=None, user=None):
        positions = self._add_extra(data['by_team'], data['top'], team, 'finish_time')
        data = {
            'positions': positions,
        }
        return super().render_data(data, team=team, user=user)
