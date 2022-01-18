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

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse


class User(AbstractUser):
    class Meta:
        db_table = 'auth_user'

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, serialize=False, unique=True)
    picture = models.URLField(blank=True, help_text='Paste a URL to an image for your profile picture')
    contact = models.BooleanField(
        null=True, help_text="We won't spam you, only important information about our events.", verbose_name='May we contact you?'
    )

    def attendance_at(self, event):
        return self.attendance_set.get(event=event)

    def get_absolute_url(self):
        return reverse('profile', kwargs={'pk': self.uuid})


# Note: UserProfile and its associated manager are slated for deletion. Any new references should be directly with the user model via
# `django.conf.settings.AUTH_USER_MODEL` or `django.contrib.auth.get_user_model()`
class UserProfileManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().select_related('user')


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
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
        warnings.warn('Attendance has been moved to User model', DeprecationWarning)
        return self.user.attendance_set.get(event=event)

    def team_at(self, event):
        if event in self._team_at:
            return self._team_at[event]
        team = self.teams.get(at_event=event)
        self._team_at[event] = team
        return team
