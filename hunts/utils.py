# Copyright (C) 2018 The Hunter2 Contributors.
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


from base64 import urlsafe_b64encode
from collections import defaultdict

from django.http import Http404


def event_episode(event, episode_number):
    from .models import Episode

    episodes = event.episode_set.order_by('start_date')
    ep_int = int(episode_number)
    try:
        ep = episodes[ep_int - 1:ep_int].get()
    except Episode.DoesNotExist as e:
        raise Http404 from e
    ep.relative_id = ep_int
    return ep


def event_episode_puzzle(event, episode_number, puzzle_number):
    from .models import Puzzle

    episode = event_episode(event, episode_number)
    try:
        return episode, episode.get_puzzle(puzzle_number)
    except Puzzle.DoesNotExist as e:
        raise Http404 from e


def finishing_positions(event):
    """Get an iterable of teams in the order in which they finished the whole Event"""
    from .models import Episode
    winning_episodes = Episode.objects.filter(event=event, winning=True)

    team_times = defaultdict(list)
    for ep in winning_episodes:
        for team, time in ep.finished_times():
            team_times[team].append(time)

    num_winning_episodes = len(winning_episodes)
    for team, times in list(team_times.items()):
        if len(times) < num_winning_episodes:
            # To win an event you have to win every winning episode
            del team_times[team]
        else:
            # Your position is dictated by the maximum of your episode win times
            team_times[team] = max(times)

    return sorted(team_times.keys(), key=lambda t: team_times[t])


def encode_uuid(uuid):
    return urlsafe_b64encode(uuid.bytes).strip(b'=').decode('ascii')
