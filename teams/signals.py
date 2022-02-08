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


from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import Team


@receiver(m2m_changed, sender=Team.members.through)
def members_changed(sender, instance, action, pk_set, **kwargs):
    User = get_user_model()

    if action == 'pre_add':
        if instance.is_full():
            raise ValidationError('Teams can have at most %d members' % instance.at_event.max_team_size)
        for user_id in pk_set:
            user = User.objects.get(pk=user_id)
            if Team.objects.exclude(pk=instance.pk).filter(at_event=instance.at_event).filter(members=user).count() > 0:
                pk_set.remove(user_id)
                raise ValidationError('User can only join one team per same event')
