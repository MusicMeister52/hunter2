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


from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import SuspiciousOperation
from django.forms.models import inlineformset_factory, modelform_factory
from django.forms.widgets import RadioSelect
from django.utils.safestring import mark_safe

from events.models import Attendance
from hunter2.models import Configuration
from . import models

CONTACT_CHOICES = [
    (True, "Yes"),
    (False, "No"),
]

UserForm = modelform_factory(User, fields=('email', ))

UserInfoFormset = inlineformset_factory(
    User, models.UserInfo, fields=('picture', 'contact'), can_delete=False, widgets={'contact': RadioSelect(choices=CONTACT_CHOICES, attrs={"required": True})}
)


def attendance_formset_factory(seat_assignments):
    fields = ('seat', ) if seat_assignments else ()
    return inlineformset_factory(models.UserInfo, Attendance, fields=fields, extra=0, can_delete=False)


class UserInfoForm(forms.ModelForm):
    class Meta:
        model = models.UserInfo
        fields = ['contact']
        widgets = {
            'contact': RadioSelect(choices=CONTACT_CHOICES, attrs={"required": True}),
        }

    field_order = ['username', 'email', 'password1', 'password2', 'contact']


class UserSignupForm(UserInfoForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if Configuration.get_solo().privacy_policy:
            self.fields['privacy'] = forms.BooleanField(
                label=mark_safe('I have read and agree to <a href="/privacy">the site privacy policy</a>'),
                required=True,
            )

    def signup(self, request, user):
        if 'privacy' in self.fields and request.POST['privacy'] != "on":
            raise SuspiciousOperation("You must accept the privacy policy")
        user.info = models.UserInfo(user=user, contact=request.POST['contact'])
        user.info.save()
        user.save()
