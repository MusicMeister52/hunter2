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


from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from accounts.models import UserProfile
from teams.models import Team
from .models import Episode, Guess, Puzzle


@receiver(m2m_changed, sender=Team.members.through)
def members_changed(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add':
        users = UserProfile.objects.filter(pk__in=pk_set)
        guesses = Guess.objects.filter(by__in=users)
        guesses.update(by_team=instance, correct_current=False)
