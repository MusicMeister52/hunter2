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


from dal import autocomplete
from django import forms

from accounts.models import UserInfo
from . import models


class InviteForm(forms.Form):
    user = forms.ModelChoiceField(
        label='Search for a user:',
        queryset=UserInfo.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='userinfo_autocomplete',
            attrs={
                'data-minimum-input-length': 1,
            },
        ),
    )


class RequestForm(forms.Form):
    team = forms.ModelChoiceField(
        label='Search for a team:',
        queryset=models.Team.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='team_autocomplete',
            attrs={
                'data-minimum-input-length': 1,
            },
        ),
    )


class CreateTeamForm(forms.ModelForm):
    """Teams are never really created explicitly. Creating a team really means giving a name to your team."""
    class Meta:
        model = models.Team
        fields = ['name']
        labels = {
            'name': 'Choose a name for your team:',
        }


class MembershipForm(forms.ModelForm):
    # Hidden unless someone tries to move a user in a way which will change team progress
    confirm_move = forms.BooleanField(required=False, widget=forms.HiddenInput(), label="Yes, move user")

    class Meta:
        model = models.Membership
        fields = ('user', 'team', 'confirm_move')

    def clean(self, **kwargs):
        cleaned_data = super().clean(**kwargs)

        # We are going to check if the admin is moving members. But only if there are no other errors.
        if self.errors:
            return cleaned_data

        old_team = self.instance.team
        new_team = cleaned_data.get('team')

        if old_team != new_team:
            print('HERE')
            if cleaned_data['confirm_move']:
                print('NO REALLY')
                return cleaned_data
            else:
                print('REALLY')
                self.fields['confirm_move'].widget = forms.CheckboxInput()
                self.add_error('confirm_move',
                               f'You are trying to move {self.instance.user} from {old_team} to {new_team}. '
                               'Are you sure you want to do this? '
                               f'Note! If {self.instance.user} already answered questions, this will most likely alter the respective teams\' progress!')
                return cleaned_data
