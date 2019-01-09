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
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from teams.models import Membership
from .models import Episode, Guess, Puzzle


@receiver(m2m_changed, sender=Episode.puzzles.through)
def episode_puzzles_changed(sender, instance, action, pk_set, **kwargs):
    if action == 'pre_add':
        for puzzle_id in pk_set:
            puzzle = Puzzle.objects.get(pk=puzzle_id)
            if puzzle.episode_set.count() > 0:
                raise ValidationError('Puzzle can only be used in one episode')


@receiver(m2m_changed, sender=Episode.prequels.through)
def episode_prequels_changed(sender, instance, action, pk_set, **kwargs):
    if action == 'pre_add':
        for episode_id in pk_set:
            episode = Episode.objects.get(pk=episode_id)
            if episode == instance:
                raise ValidationError('Episode cannot follow itself')
            elif episode.follows(instance):
                raise ValidationError('Circular dependency found in episodes')


@receiver(post_save, sender=Membership)
def membership_changed(sender, instance, created, raw, using, update_fields, **kwargs):
    guesses = Guess.objects.filter(by=instance.user.user.profile)
    guesses.update(by_team=instance.team, correct_current=False)
