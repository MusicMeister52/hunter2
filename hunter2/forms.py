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
from django.contrib.sites.models import Site
from django import forms
from django.forms import ModelForm

from events.models import Event


class SiteForm(ModelForm):
    class Meta:
        model = Site
        fields = ['name', 'domain']


class EventForm(ModelForm):
    subdomain = forms.CharField(max_length=255, help_text="Sub-domain to use for the event")

    class Meta:
        model = Event
        fields = ['name']

