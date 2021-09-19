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


from django.db.models import Count, Q
from schema import Schema

from accounts.models import UserProfile
from hunts.models import Guess
from teams.models import Team, TeamRole
from .abstract import AbstractGenerator


class TotalsGenerator(AbstractGenerator):
    """
    Generates headline participation statistics

    Outputs the following aggregates:
        - Active Players - The number of users who were part of a team which submitted at least one guess.
        - Active Teams   - The number of teams who submitted at least one guess.
        - Correct Teams  - The number of teams which correctly solved at least one puzzle.
        - Guess Count    - The total number of guesses submitted by all players and teams.
    """
    title = 'Totals'
    version = 1

    schema = Schema({
        'active_players': int,
        'active_teams': int,
        'correct_teams': int,
        'guess_count': int,
    })

    def generate(self):
        if self.episode is not None:
            guesses_filter = Q(for_puzzle__episode=self.episode)
            team_guesses_filter = Q(guess__for_puzzle__episode=self.episode)
        else:
            guesses_filter = Q()
            team_guesses_filter = Q()
        teams = Team.objects.filter(role=TeamRole.PLAYER).annotate(
            guesses=Count('guess', filter=team_guesses_filter),
            correct_guesses=Count('guess', filter=team_guesses_filter & Q(guess__correct_for__isnull=False, guess__correct_current=True)),
        )
        active_teams = teams.filter(guesses__gt=0)
        correct_teams = active_teams.filter(correct_guesses__gt=0)
        active_players = UserProfile.objects.filter(teams__in=active_teams)
        guesses = Guess.objects.filter(guesses_filter & Q(by_team__role=TeamRole.PLAYER))
        return {
            'active_players': active_players.count(),
            'active_teams': active_teams.count(),
            'correct_teams': correct_teams.count(),
            'guess_count': guesses.count()
        }
