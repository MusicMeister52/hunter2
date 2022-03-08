# Copyright (C) 2018-2022 The Hunter2 Contributors.
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


from allauth.account import views as allauth_views
from allauth.account.forms import ChangePasswordForm, SetPasswordForm
from dal import autocomplete
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic.detail import DetailView
from django_tenants.utils import tenant_context

from teams.models import Team, TeamRole
from . import forms


User = get_user_model()


class UserAutoComplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    raise_exception = True

    def get_result_value(self, result):
        return str(result.uuid)

    def get_queryset(self):
        qs = User.objects.exclude(pk=self.request.user.pk).order_by('username')

        if self.q:
            qs = qs.filter(
                Q(username__istartswith=self.q) |
                Q(email__istartswith=self.q)
            )

        return qs


class ProfileView(DetailView):
    model = User
    slug_field = 'uuid'
    slug_url_kwarg = 'uuid'
    template_name = 'accounts/profile.html'

    def get_context_data(self, object):
        context = super().get_context_data(object=object)
        context.update({
            'authorships': [],
            'administrations': [],
            'participations': [],
        })
        context_keys = {
            TeamRole.AUTHOR: 'authorships',
            TeamRole.ADMIN: 'administrations',
            TeamRole.PLAYER: 'participations',
        }
        for attendance in object.attendance_set.all().order_by('-event__end_date').select_related('event'):
            event = attendance.event
            with tenant_context(event):
                try:
                    team = Team.objects.filter(members=object).get()
                    attendance_info = {
                        "event": event.name,
                        "team": team.name,
                    }
                    context[context_keys[team.role]].append(attendance_info)
                except Team.DoesNotExist:
                    pass
        return context


class PasswordChangeView(allauth_views.PasswordChangeView):
    success_url = reverse_lazy('edit_profile')


class EditProfileView(LoginRequiredMixin, View):
    def _get_attendance_formset(self, request):
        AttendanceFormset = forms.attendance_formset_factory(request.tenant.seat_assignments)
        return AttendanceFormset(instance=request.user, queryset=request.user.attendance_set.filter(event=request.tenant))

    def _render(self, request, user_form, attendance_formset):
        password_form = ChangePasswordForm(user=request.user) if request.user.has_usable_password() else SetPasswordForm(user=request.user)
        steam_account = request.user.socialaccount_set.first()  # This condition breaks down if we support multiple social accounts.
        if steam_account:
            steam_account = steam_account.uid.replace('openid/id', 'profiles')  # This is heavily steam specific
        context = {
            'user_form': user_form,
            'password_form': password_form,
            'attendance_formset': attendance_formset,
            'steam_account': steam_account,
        }
        return TemplateResponse(
            request,
            'accounts/profile_edit.html',
            context=context,
        )

    def get(self, request):
        user_form = forms.UserForm(instance=request.user)
        attendance_formset = self._get_attendance_formset(request) if request.tenant else None
        return self._render(request, user_form, attendance_formset)

    def post(self, request):
        user_form = forms.UserForm(request.POST, instance=request.user)
        attendance_formset = None
        if user_form.is_valid():
            created_user = user_form.save(commit=False)
            AttendanceFormset = forms.attendance_formset_factory(request.tenant.seat_assignments)
            attendance_formset = AttendanceFormset(request.POST, instance=created_user)
            if attendance_formset.is_valid():
                created_user.save()
                attendance_formset.save()
                return HttpResponseRedirect(reverse('edit_profile'))
        if not attendance_formset and request.tenant:
            attendance_formset = self._get_attendance_formset(request)
        return self._render(request, user_form, attendance_formset)
