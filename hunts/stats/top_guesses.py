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

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from schema import And, Schema

from teams.models import Team, TeamRole
from .abstract import AbstractGenerator


class TopGuessesGenerator(AbstractGenerator):
    """
    Generates table of the top guessing users and teams

    Guess counts are aggregated by user and team and those who submitted the most guesses are included in the output.
    """
    title = 'Most Guesses'
    version = 1

    _by_entity_schema = Schema({
        'position': int,
        'guess_count': datetime,
    })

    _top_entry_schema = Schema((
                int,
                And(str, len),
                datetime,
    ))

    schema = Schema({
        'by_team': {
            And(str, len): _by_entity_schema,
        },
        'by_user': {
            And(str, len): _by_entity_schema,
        },
        'top_teams': [
            _top_entry_schema,
        ],
        'top_users': [
            _top_entry_schema,
        ],
    })

    def __init__(self, number=10, **kwargs):
        super().__init__(**kwargs)
        self._number = number

    def generate(self):
        User = get_user_model()
        if self.episode is not None:
            guesses_filter = Q(guess__for_puzzle__episode=self.episode)
        else:
            guesses_filter = Q()
        teams = Team.objects.filter(role=TeamRole.PLAYER).annotate(guess_count=Count('guess', filter=guesses_filter)).order_by('-guess_count')
        users = User.objects.filter(teams__role=TeamRole.PLAYER).annotate(guess_count=Count('guess', filter=guesses_filter)).order_by('-guess_count')
        return {
            'by_team': {
                team.id: {
                    'position': position,
                    'guess_count': team.guess_count,
                } for position, team in enumerate(teams, start=1)
            },
            'top_teams': [
                (
                    position,
                    team.get_display_name(),
                    team.guess_count,
                ) for position, team in enumerate(teams[:self._number], start=1)
            ],
            'by_user': {
                user.id: {
                    'position': position,
                    'guess_count': user.guess_count,
                } for position, user in enumerate(users, start=1)
            },
            'top_users': [
                (
                    position,
                    user.username,
                    user.guess_count,
                ) for position, user in enumerate(users[:self._number], start=1)
            ],
        }

    def render_data(self, data, team=None, user=None):
        data = {
            'teams': self._add_extra(data['by_team'], data['top_teams'], team, 'guess_count'),
            'users': self._add_extra(data['by_user'], data['top_users'], user, 'guess_count'),
        }
        return super().render_data(data, team=team, user=user)
