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
import warnings

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class UserProfileManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('user')


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    objects = UserProfileManager()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._team_at = {}

    @property
    def username(self):
        return self.user.username

    def get_display_name(self):
        return self.user.username

    def __str__(self):
        return f'{self.username}'

    def is_on_explicit_team(self, event):
        return self.teams.filter(at_event=event).exclude(name=None).exists()

    def attendance_at(self, event):
        warnings.warn('Attendance has been moved to UserInfo model', DeprecationWarning)
        return self.user.info.attendance_set.get(event=event)

    def team_at(self, event):
        if event in self._team_at:
            return self._team_at[event]
        team = self.teams.get(at_event=event)
        self._team_at[event] = team
        return team


# Today this is a new model because it needs an unenumerable key since it will be used in a URL.
# Later we will migrate references to users to use this model too and deprecate UserProfile
class UserInfo(models.Model):
    class Manager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().select_related('user')

    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='info')
    picture = models.URLField(blank=True, help_text='Paste a URL to an image for your profile picture')
    contact = models.BooleanField(
        null=True, help_text="We won't spam you, only important information about our events.", verbose_name='May we contact you?'
    )
    objects = Manager()

    @property
    def username(self):
        return self.user.username

    def attendance_at(self, event):
        return self.attendance_set.get(event=event)

    def get_absolute_url(self):
        return reverse('profile', kwargs={'pk': self.id})
