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


import uuid


from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

import accounts
import events


class Team(models.Model):
    # Nullable CharField with the unique property allows us to enforce uniqueness at DB schema level
    # DB will allow multiple teams with no name while still enforcing name uniqueness
    name = models.CharField(blank=True, null=True, unique=True, max_length=100)
    at_event = models.ForeignKey(events.models.Event, on_delete=models.DO_NOTHING, related_name='teams')
    is_admin = models.BooleanField(default=False)
    members = models.ManyToManyField(accounts.models.UserProfile, blank=True, related_name='teams')
    invites = models.ManyToManyField(accounts.models.UserProfile, blank=True, related_name='team_invites')
    requests = models.ManyToManyField(accounts.models.UserProfile, blank=True, related_name='team_requests')

    def __str__(self):
        return '%s @%s' % (self.get_verbose_name(), self.at_event)

    def get_verbose_name(self):
        if self.is_explicit():
            return self.name
        if self.members.all().count() == 1:
            # We use .all()[0] to allow for prefetch_related
            return '[%s\'s team]' % (self.members.all()[0])
        elif self.members.all().count() == 0:
            return '[empty anonymous team]'
        else:
            # This should never happen but we don't want things to break if it does!
            return '[anonymous team with %d members!]' % self.members.count()

    def clean(self):
        if (
            self.is_admin and
            Team.objects.exclude(id=self.id).filter(at_event=self.at_event).filter(is_admin=True).count() > 0
        ):
            raise ValidationError('There can only be one admin team per event')

    def save(self, *args, **kwargs):
        # We don't want to use '' as our empty value because we would trip over the uniqueness constraint
        if self.name == '':
            self.name = None
        return super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('team', kwargs={'team_id': self.pk})

    def is_explicit(self):
        return self.name is not None

    def is_full(self):
        return self.members.count() >= self.at_event.max_team_size > 0 and not self.is_admin


class Membership(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.OneToOneField(accounts.models.UserInfo)
    team = models.ForeignKey(Team)


class Invite(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    by = models.ForeignKey(accounts.models.UserInfo)
    user = models.ForeignKey(accounts.models.UserInfo)
    team = models.ForeignKey(Team)


class Request(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.ForeignKey(accounts.models.UserInfo)
    team = models.ForeignKey(Team)
