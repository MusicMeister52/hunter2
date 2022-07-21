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
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, UpdateView

from events.utils import annotate_user_queryset_with_seat
from hunter2.mixins import APITokenRequiredMixin
from . import forms, models
from .forms import CreateTeamForm, InviteForm, RequestForm

import json


class TeamAutoComplete(LoginRequiredMixin, autocomplete.Select2QuerySetView):
    raise_exception = True

    def get_queryset(self):
        qs = models.Team.objects.filter(at_event=self.request.tenant).order_by('name')

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs


class CreateTeamView(LoginRequiredMixin, UpdateView):
    form_class = forms.CreateTeamForm
    template_name = 'teams/create.html'

    def get_object(self):
        return self.request.team

    def get_success_url(self):
        team_id = self.request.team.pk
        return reverse('team', kwargs={'team_id': team_id})


class ManageTeamView(LoginRequiredMixin, TemplateView):
    template_name = "teams/manage.html"

    def get_context_data(self, **kwargs):
        request = self.request
        if request.team.is_explicit():
            invite_form = InviteForm()
            invites = annotate_user_queryset_with_seat(request.team.invites, request.tenant)
            members = annotate_user_queryset_with_seat(request.team.members, request.tenant)
            requests = annotate_user_queryset_with_seat(request.team.requests, request.tenant)
            context = {
                'invite_form': invite_form,
                'invites': invites,
                'members': members,
                'requests': requests,
            }
        else:
            invites = models.Team.objects.filter(invites=request.user)
            requests = models.Team.objects.filter(requests=request.user)
            create_form = CreateTeamForm(instance=request.team)
            request_form = RequestForm()
            context = {
                'invites': invites,
                'requests': requests,
                'create_form': create_form,
                'request_form': request_form,
            }
        context['token'] = request.team.token
        if request.tenant:
            context['discord_url'] = request.tenant.discord_url
            context['discord_bot_id'] = request.tenant.discord_bot_id
        return context


class TeamView(LoginRequiredMixin, View):
    def get(self, request, team_id):
        team = get_object_or_404(
            models.Team, at_event=request.tenant, pk=team_id
        )
        if not team.name:
            raise Http404
        else:
            members = annotate_user_queryset_with_seat(team.members, request.tenant)

            return TemplateResponse(
                request,
                'teams/view.html',
                context={
                    'team': team.name,
                    'members': members,
                    'invited': request.user in team.invites.all(),
                    'requested': request.user in team.requests.all(),
                }
            )


class Invite(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user
        if user not in team.members.all():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a member to invite to a team',
            }, status=403)
        User = get_user_model()
        try:
            user = User.objects.get(uuid=data['user'])
        except ValidationError:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Invalid User UUID',
            }, status=400)
        except User.DoesNotExist:
            return JsonResponse({
                'result': 'Not Found',
                'message': 'User does not exist',
            }, status=404)
        if user in team.invites.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has already been invited',
            }, status=400)
        if user.is_on_explicit_team(request.tenant):
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User is already a member of a team for this event',
            }, status=400)
        if team.is_full():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
            }, status=400)
        team.invites.add(user)
        return JsonResponse({
            'result': 'OK',
            'message': 'User invited',
            'username': user.username,
        })


class CancelInvite(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        if request.user not in team.members.all():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a team member to cancel an invite',
            }, status=403)
        User = get_user_model()
        try:
            user = User.objects.get(uuid=data['user'])
        except ValidationError:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Invalid User UUID',
            }, status=400)
        except User.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User does not exist',
                'delete': True,
            }, status=400)
        if user not in team.invites.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has not been invited',
                'delete': True,
            }, status=400)
        team.invites.remove(user)
        return JsonResponse({
            'result': 'OK',
            'message': 'Invite cancelled',
        })


class AcceptInvite(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user
        if user not in team.invites.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Not invited to this team',
                'delete': True,
            }, status=400)
        if user.is_on_explicit_team(request.tenant):
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already on a team for this event',
                'delete': True,
            }, status=400)
        if team.is_full():
            team.invites.remove(user)
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
                'delete': True,
            }, status=400)
        old_team = request.user.team_at(request.tenant)
        old_team.guess_set.update(by_team=team)
        old_team.delete()  # This is the user's implicit team, as checked above.
        user.team_invites.remove(*user.team_invites.filter(at_event=request.tenant))
        user.team_requests.remove(*user.team_requests.filter(at_event=request.tenant))
        team.members.add(user)
        return JsonResponse({
            'result': 'OK',
            'message': 'Invite accepted',
        })


class DenyInvite(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user
        if user not in team.invites.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'You have not been invited',
                'delete': True,
            }, status=400)
        team.invites.remove(user)
        return JsonResponse({
            'result': 'OK',
            'message': 'Invite denied',
        })


class Request(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user
        if user.is_on_explicit_team(request.tenant):
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already a member of a team for this event',
            }, status=400)
        if user in team.requests.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already requested',
            }, status=400)
        if team.is_full():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
            }, status=400)
        team.requests.add(user)
        return JsonResponse({
            'result': 'OK',
            'message': 'Requested',
            'team': team.name,
        })


class CancelRequest(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        user = request.user
        if user not in team.requests.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Request does not exist',
                'delete': True,
            }, status=400)
        team.requests.remove(user)
        return JsonResponse({
            'result': 'OK',
            'message': 'Requested cancelled',
        })


class AcceptRequest(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        if request.user not in team.members.all():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a team member to accept an request',
            }, status=403)
        User = get_user_model()
        try:
            user = User.objects.get(uuid=data['user'])
        except ValidationError:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Invalid User UUID',
            }, status=400)
        except User.DoesNotExist:
            return JsonResponse({
                'result': 'Not Found',
                'message': 'User does not exist',
                'delete': True,
            }, status=404)
        if user not in team.requests.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has not requested to join',
                'delete': True,
            }, status=400)
        if user.is_on_explicit_team(request.tenant):
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Already a member of a team for this event',
                'delete': True,
            }, status=403)
        if team.is_full():
            team.requests.remove(user)
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'This team is full',
                'delete': True,
            }, status=400)
        old_team = user.team_at(request.tenant)
        old_team.guess_set.update(by_team=team)
        old_team.delete()  # This is the user's implicit team, as checked above.
        user.team_invites.remove(*user.team_invites.filter(at_event=request.tenant))
        user.team_requests.remove(*user.team_requests.filter(at_event=request.tenant))
        team.members.add(user)
        seat = user.attendance_at(request.tenant).seat
        return JsonResponse({
            'result': 'OK',
            'message': 'Request accepted',
            'username': user.username,
            'seat': seat,
            'url': user.get_absolute_url(),
            'picture': user.picture,
        })


class DenyRequest(LoginRequiredMixin, View):
    raise_exception = True

    def post(self, request, team_id):
        data = json.loads(request.body)
        team = get_object_or_404(models.Team, at_event=request.tenant, pk=team_id)
        User = get_user_model()
        try:
            user = User.objects.get(uuid=data['user'])
        except ValidationError:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Invalid User UUID',
            }, status=400)
        except User.DoesNotExist:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User does not exist',
                'delete': True,
            }, status=400)
        if request.user not in team.members.all():
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be a team member to deny a request',
            }, status=403)
        if user not in team.requests.all():
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'User has not requested to join',
                'delete': True,
            }, status=400)
        team.requests.remove(user)
        return JsonResponse({
            'result': 'OK',
            'message': 'Request denied',
        })


class TeamListView(APITokenRequiredMixin, View):
    def get(self, request):
        plain = False
        # Very basic Accept header handling
        # If the header is present and contains text/plain then return that, otherwise return JSON
        # This can be expanded if we want to support more API paths and/or more formats or if we ever want to respect q values
        accepts = request.META.get('HTTP_ACCEPT')
        if accepts is not None:
            for media in accepts.split(','):
                if media.strip().split(';')[0].strip() == 'text/plain':
                    plain = True
                    break
        teams = models.Team.objects.all().prefetch_related('members').seal()
        if plain:
            return HttpResponse("\n".join(t.get_unique_ascii_name() for t in teams))
        return JsonResponse({
            'items': [{
                'id': t.id,
                'type': 'team' if t.is_explicit() else 'player',
                'name': t.get_display_name(),
            } for t in teams],
        })


class TeamInfoView(APITokenRequiredMixin, View):
    def get(self, request, team_token):
        try:
            team = models.Team.objects.get(token=team_token)
        except models.Team.DoesNotExist:
            return JsonResponse({
                'result': 'Not Found',
                'message': 'Invalid team token',
            }, status=404)
        return JsonResponse({
            'result': 'OK',
            'team': {
                'name': team.name,
            },
        })
