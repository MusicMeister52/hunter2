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
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views import View
from django.views.generic import UpdateView

from accounts.models import UserInfo
from events.models import Attendance
from events.utils import annotate_userinfo_queryset_with_seat
from . import forms, models
from .forms import CreateTeamForm, InviteForm, RequestForm
from .mixins import TeamMixin

import json


class TeamAutoComplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    raise_exception = True

    def get_queryset(self):
        qs = models.Team.objects.filter(at_event=self.request.tenant).order_by('name')

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs


class CreateTeamView(LoginRequiredMixin, TeamMixin, UpdateView):
    form_class = forms.CreateTeamForm
    template_name = 'teams/create.html'

    def get_object(self):
        return self.request.team

    def get_success_url(self):
        team_id = self.request.team.pk
        return reverse('team', kwargs={'team_id': team_id})


class ManageTeamView(LoginRequiredMixin, TeamMixin, View):
    def get(self, request):
        if request.team.is_explicit():
            invite_form = InviteForm()
            invites = annotate_userinfo_queryset_with_seat(UserInfo.objects.filter(invite__in=request.team.invite_set.all()), request.tenant)
            members = annotate_userinfo_queryset_with_seat(UserInfo.objects.filter(membership__in=request.team.membership_set.all()), request.tenant)
            requests = annotate_userinfo_queryset_with_seat(UserInfo.objects.filter(request__in=request.team.request_set.all()), request.tenant)
            context = {
                'invite_form': invite_form,
                'invites': invites,
                'members': members,
                'requests': requests,
            }
        else:
            invites = models.Team.objects.filter(invite__user=request.user.info)
            requests = models.Team.objects.filter(request__user=request.user.info)
            create_form = CreateTeamForm(instance=request.team)
            request_form = RequestForm()
            context = {
                'invites': invites,
                'requests': requests,
                'create_form': create_form,
                'request_form': request_form,
            }
        return TemplateResponse(
            request,
            'teams/manage.html',
            context=context,
        )


class TeamView(LoginRequiredMixin, TeamMixin, View):
    def get(self, request, team_id):
        team = get_object_or_404(
            models.Team, at_event=request.tenant, pk=team_id
        )
        if not team.name:
            raise Http404
        else:
            members = annotate_userinfo_queryset_with_seat(UserInfo.objects.filter(membership__in=team.membership_set.all()), request.tenant)

            return TemplateResponse(
                request,
                'teams/view.html',
                context={
                    'team': team.name,
                    'members': members,
                    'invited': request.user.profile in team.invite_set.all(),
                    'requested': request.user.profile in team.request_set.all(),
                }
            )


class Invite(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        inviter = request.user.info
        if not team.membership_set.filter(user=inviter).exists():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a member to invite to a team',
            }, status=403)
        try:
            invitee = UserInfo.objects.get(pk=data['user'])
        except UserInfo.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User does not exist',
            }, status=400)
        if models.Invite.objects.filter(team=team, user=invitee).exists():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has already been invited',
            }, status=400)
        if invitee.is_on_explicit_team():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User is already a member of a team for this event',
            }, status=400)
        if team.is_full():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
            }, status=400)
        models.Invite(team=team, by=inviter, user=invitee).save()
        return JsonResponse({
            'result': 'OK',
            'message': 'User invited',
            'username': invitee.username,
        })


class CancelInvite(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        if not team.membership_set.filter(user=request.user.info).exists():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a team member to cancel an invite',
            }, status=403)
        try:
            invitee = UserInfo.objects.get(pk=data['user'])
        except UserInfo.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User does not exist',
                'delete': True,
            }, status=400)
        try:
            invite = invitee.invite_set.get(team=team)
        except models.Invite.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has not been invited',
                'delete': True,
            }, status=400)
        invite.delete()
        return JsonResponse({
            'result': 'OK',
            'message': 'Invite cancelled',
        })


class AcceptInvite(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user.info
        try:
            invite = user.invite_set.get(team=team)
        except models.Invite.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Not invited to this team',
                'delete': True,
            }, status=400)
        if user.is_on_explicit_team():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already on a team for this event',
                'delete': True,
            }, status=400)
        if team.is_full():
            invite.delete()
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
                'delete': True,
            }, status=400)
        try:
            old_team = user.membership.team
            old_team.guess_set.update(by_team=team)
            old_team.delete()  # This is the user's implicit team, as checked above.
        except UserInfo.membership.RelatedObjectDoesNotExist:
            pass
        user.invite_set.filter(team__at_event=request.tenant).delete()  # xxx(Conan): needs a test
        user.request_set.filter(team__at_event=request.tenant).delete()  # xxx(Conan): needs a test
        models.Membership(team=team, user=user).save()
        return JsonResponse({
            'result': 'OK',
            'message': 'Invite accepted',
        })


class DenyInvite(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user.info
        try:
            invite = user.invite_set.get(team=team)
        except models.Invite.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'You have not been invited',
                'delete': True,
            }, status=400)
        invite.delete()
        return JsonResponse({
            'result': 'OK',
            'message': 'Invite denied',
        })


class Request(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user.info
        if user.is_on_explicit_team():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already a member of a team for this event',
            }, status=400)
        if models.Request.objects.filter(team=team, user=user).exists():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already requested',
            }, status=400)
        if team.is_full():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
            }, status=400)
        models.Request(team=team, user=user).save()
        return JsonResponse({
            'result': 'OK',
            'message': 'Requested',
            'team': team.name,
        })


class CancelRequest(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user.info
        try:
            request = team.request_set.get(user=user)
        except models.Request.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Request does not exist',
                'delete': True,
            }, status=400)
        request.delete()
        return JsonResponse({
            'result': 'OK',
            'message': 'Requested cancelled',
        })


class AcceptRequest(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        event = request.tenant
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=event, pk=team_id)
        if not team.membership_set.filter(user=request.user.info).exists():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a team member to accept an request',
            }, status=403)
        try:
            user = UserInfo.objects.get(pk=data['user'])
        except UserInfo.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User does not exist',
                'delete': True,
            }, status=400)
        try:
            request = team.request_set.get(user=user)
        except models.Request.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has not requested to join',
                'delete': True,
            }, status=400)
        if user.is_on_explicit_team():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already a member of a team for this event',
                'delete': True,
            }, status=403)
        if team.is_full():
            request.delete()
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
                'delete': True,
            }, status=400)
        try:
            old_team = user.membership.team
            old_team.guess_set.update(by_team=team)
            old_team.delete()  # This is the user's implicit team, as checked above.
        except UserInfo.membership.RelatedObjectDoesNotExist:
            pass  # We ought to have been put on an implicit team by now, but there's no reason to require it here
        user.invite_set.filter(team__at_event=event).delete()
        user.request_set.filter(team__at_event=event).delete()
        models.Membership(team=team, user=user).save()
        try:
            seat = user.attendance_at(event).seat
        except Attendance.DoesNotExist:
            seat = ''  # Default in case they somehow don't have an Attendance yet
        return JsonResponse({
            'result': 'OK',
            'message': 'Request accepted',
            'username': user.username,
            'seat': seat,
        })


class DenyRequest(LoginRequiredMixin, TeamMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        if not team.membership_set.filter(user=request.user.info).exists():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a team member to deny an request',
            }, status=403)
        try:
            user = UserInfo.objects.get(pk=data['user'])
        except UserInfo.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User does not exist',
                'delete': True,
            }, status=400)
        try:
            request = team.request_set.get(user=user)
        except models.Request.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has not requested to join',
                'delete': True,
            }, status=400)
        request.delete()
        return JsonResponse({
            'result': 'OK',
            'message': 'Request denied',
        })
