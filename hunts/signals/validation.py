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


from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from ..models import Episode


@receiver(m2m_changed, sender=Episode.prequels.through)
def episode_prequels_changed(sender, instance, action, pk_set, **kwargs):
    if action == 'pre_add':
        for episode_id in pk_set:
            episode = Episode.objects.get(pk=episode_id)
            if episode == instance:
                raise ValidationError('Episode cannot follow itself')
            elif episode.follows(instance):
                raise ValidationError('Circular dependency found in episodes')
