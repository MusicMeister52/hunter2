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


from teams.models import Team

import rules


@rules.predicate
def is_admin_for_event(user, event):
    try:
        admin_team = event.teams.filter(is_admin=True).get()
    except Team.DoesNotExist:
        return False
    return user.info.membership in admin_team.membership_set.all()


rules.add_perm('hunts.change_event', is_admin_for_event)


@rules.predicate
def is_admin_for_episode(user, episode):
    return is_admin_for_event(user, episode.event)


rules.add_perm('hunts.change_episode', is_admin_for_episode)
rules.add_perm('hunts.delete_episode', is_admin_for_episode)


@rules.predicate
def is_admin_for_puzzle(user, puzzle):
    return is_admin_for_episode(user, puzzle.episode)


rules.add_perm('hunts.change_puzzle', is_admin_for_puzzle)
rules.add_perm('hunts.delete_puzzle', is_admin_for_puzzle)


@rules.predicate
def is_admin_for_clue(user, clue):
    return is_admin_for_puzzle(user, clue.puzzle)


rules.add_perm('hunts.change_hint', is_admin_for_clue)
rules.add_perm('hunts.delete_hint', is_admin_for_clue)
rules.add_perm('hunts.change_unlock', is_admin_for_clue)
rules.add_perm('hunts.delete_unlock', is_admin_for_clue)


@rules.predicate
def is_user_for_userdata(user, userdata):
    return user is userdata.user


rules.add_perm('hunts.change_userdata', is_user_for_userdata)
rules.add_perm('hunts.delete_userdata', is_user_for_userdata)


@rules.predicate
def is_user_for_teamdata(user, teamdata):
    return user in teamdata.team.users


rules.add_perm('hunts.change_teamdata', is_user_for_teamdata)
rules.add_perm('hunts.delete_teamdata', is_user_for_teamdata)
