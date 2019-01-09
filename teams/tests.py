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


import json

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.urls import reverse
from django.views import View
from django_tenants.test.client import TenantRequestFactory
from faker import Faker

from accounts.factories import UserFactory, UserInfoFactory
from accounts.models import UserInfo, UserProfile
from events.factories import EventFactory
from events.models import Event
from events.test import EventAwareTestCase, EventTestCase
from .factories import InviteFactory, MembershipFactory, RequestFactory, TeamFactory, TeamMemberFactory
from .mixins import TeamMixin
from .models import Membership, Team


class FactoryTests(EventTestCase):

    def test_team_factory_default_construction(self):
        TeamFactory.create()

    def test_membership_factory_default_construction(self):
        MembershipFactory.create()

    def test_invite_factory_default_construction(self):
        InviteFactory.create()

    def test_request_factory_default_construction(self):
        RequestFactory.create()

    def test_team_member_factory_default_construction(self):
        TeamMemberFactory.create()


class TeamNameTests(EventTestCase):
    def test_named_team_name(self):
        team = TeamFactory()
        self.assertEqual(team.get_verbose_name(), team.name)

    def test_empty_anonymous_team_name(self):
        team = TeamFactory(name=None)
        self.assertEqual(team.get_verbose_name(), '[empty anonymous team]')

    def test_single_player_team_name(self):
        team = TeamFactory(name=None)
        membership = MembershipFactory(team=team)
        self.assertEqual(team.get_verbose_name(), f'[{membership.user.username}\'s team]')

    def test_multiple_players_anonymous_team_name(self):
        event = EventFactory()
        count = Faker().random_int(min=2, max=event.max_team_size)
        team = TeamFactory(name=None)
        MembershipFactory.create_batch(count, team=team)
        self.assertEqual(team.get_verbose_name(), f'[anonymous team with {count} members!]')


class EmptyTeamView(TeamMixin, View):
    def get(self, request, *args, **kwargs):
        return HttpResponse()


class TeamMultiEventTests(EventAwareTestCase):
    def test_team_name_uniqueness(self):
        old_event = EventFactory()
        new_event = EventFactory(current=False)

        old_event.activate()
        team1 = TeamFactory(at_event=old_event)

        # Check that creating a team with the same name on the old event is not allowed.
        with self.assertRaises(ValidationError):
            TeamFactory(name=team1.name, at_event=old_event)

        new_event.activate()
        # Check that the new event team does not raise a validation error
        TeamFactory(name=team1.name, at_event=new_event)

        new_event.deactivate()


class TeamRulesTests(EventTestCase):
    def test_max_team_size(self):
        event = EventFactory()
        team = TeamFactory(at_event=event)

        MembershipFactory.create_batch(event.max_team_size, team=team)
        with self.assertRaises(ValidationError):
            MembershipFactory(team=team)

    def test_one_team_per_member_per_event(self):
        event = self.tenant
        teams = TeamFactory.create_batch(2, at_event=event)
        user = UserInfoFactory()

        Membership(team=teams[0], user=user).save()
        with self.assertRaises(ValidationError):
            Membership(team=teams[1], user=user).save()


class TeamPageTests(EventTestCase):
    def test_anonymous_team_view(self):
        member = MembershipFactory(team__at_event=self.tenant, team__name='')

        self.client.force_login(member.user.user)
        response = self.client.get(reverse('manage_team'))
        self.assertEqual(response.status_code, 200)

        # No team page for anonymous teams
        response = self.client.get(reverse('team', kwargs={'team_id': member.team.id}))
        self.assertEqual(response.status_code, 404)

    def test_named_team_view(self):
        member = MembershipFactory(team__at_event=self.tenant)

        self.client.force_login(member.user.user)
        response = self.client.get(reverse('manage_team'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('team', kwargs={'team_id': member.team.id}))
        self.assertEqual(response.status_code, 200)


class TeamCreateTests(EventTestCase):
    def test_team_create(self):
        creator = UserInfoFactory()
        team_template = TeamFactory.build()

        self.client.force_login(creator.user)
        response = self.client.post(
            reverse('create_team'),
            {
                'name': team_template.name,
            },
        )
        self.assertEqual(response.status_code, 302)
        team = Team.objects.get(name=team_template.name)
        self.assertTrue(team.membership_set.filter(user=creator).exists())

    def test_automatic_creation(self):
        factory = TenantRequestFactory(self.tenant)
        request = factory.get('/irrelevant')  # Path is not used because we call the view function directly
        request.tenant = Event.objects.get()
        request.user = UserFactory()
        view = EmptyTeamView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 200)
        user = UserInfo.objects.get(user=request.user)
        UserProfile.objects.get(user=request.user)
        Membership.objects.get(user=user)


class InviteTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.inviter = UserInfoFactory()
        self.invitee = UserInfoFactory()
        self.team = TeamFactory(at_event=self.event, members={self.inviter})

    def test_invite_create(self):
        # Create an invite for the "invitee" user using the "inviter" account.
        self.client.force_login(self.inviter.user)
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.invitee.id)
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.team.invite_set.filter(user=self.invitee).exists())

    def test_invite_accept(self):
        InviteFactory(team=self.team, by=self.inviter, user=self.invitee)
        self.client.force_login(self.invitee.user)
        response = self.client.post(
            reverse('acceptinvite', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.team.membership_set.filter(user=self.invitee).exists())
        self.assertFalse(self.team.invite_set.filter(user=self.invitee).exists())

    def test_invite_to_full_team(self):
        self.event.max_team_size = 1
        self.event.save()
        self.client.force_login(self.inviter.user)
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.invitee.id)
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.team.membership_set.filter(user=self.invitee).exists())
        self.assertFalse(self.team.invite_set.filter(user=self.invitee).exists())

    def test_accept_invite_to_full_team(self):
        self.event.max_team_size = 1
        self.event.save()
        InviteFactory(team=self.team, by=self.inviter, user=self.invitee)
        self.client.force_login(self.invitee.user)
        response = self.client.post(
            reverse('acceptinvite', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.team.membership_set.filter(user=self.invitee).exists())
        # Check we cleaned up the invite after failing
        self.assertFalse(self.team.invite_set.filter(user=self.invitee).exists())

    def test_invite_cancel(self):
        InviteFactory(team=self.team, by=self.inviter, user=self.invitee)
        self.client.force_login(self.inviter.user)
        response = self.client.post(
            reverse('cancelinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.invitee.id)
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.team.membership_set.filter(user=self.invitee).exists())
        self.assertFalse(self.team.invite_set.filter(user=self.invitee).exists())

    def test_invite_deny(self):
        InviteFactory(team=self.team, by=self.inviter, user=self.invitee)
        self.client.force_login(self.invitee.user)
        response = self.client.post(
            reverse('denyinvite', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.team.membership_set.filter(user=self.invitee).exists())
        self.assertFalse(self.team.invite_set.filter(user=self.invitee).exists())

    def test_invite_views_forbidden(self):
        self.client.logout()
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.inviter.id)
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('cancelinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.inviter.id)
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('acceptinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.inviter.id)
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('denyinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.inviter.id)
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


class RequestTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.member = UserInfoFactory()
        self.applicant = UserInfoFactory()
        self.team = TeamFactory(at_event=self.event, members={self.member})

    def test_request_create(self):
        # The "applicant" is requesting a place on "team".
        self.client.force_login(self.applicant.user)
        response = self.client.post(
            reverse('request', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.team.request_set.filter(user=self.applicant).exists())

    def test_request_accept(self):
        RequestFactory(team=self.team, user=self.applicant)
        self.client.force_login(self.member.user)
        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.applicant.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.team.membership_set.filter(user=self.applicant).exists())
        self.assertFalse(self.team.request_set.filter(user=self.applicant).exists())

    def test_request_to_full_team(self):
        self.event.max_team_size = 1
        self.event.save()
        self.client.force_login(self.applicant.user)
        response = self.client.post(
            reverse('request', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.team.membership_set.filter(user=self.applicant).exists())
        self.assertFalse(self.team.request_set.filter(user=self.applicant).exists())

    def test_accept_request_to_full_team(self):
        self.event.max_team_size = 1
        self.event.save()
        RequestFactory(team=self.team, user=self.applicant)
        self.client.force_login(self.member.user)
        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.applicant.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.team.membership_set.filter(user=self.applicant).exists())
        # Check we cleaned up the request after failing
        self.assertFalse(self.team.request_set.filter(user=self.applicant).exists())

    def test_request_cancel(self):
        RequestFactory(team=self.team, user=self.applicant)
        self.client.force_login(self.applicant.user)
        response = self.client.post(
            reverse('cancelrequest', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.team.membership_set.filter(user=self.applicant).exists())
        self.assertFalse(self.team.request_set.filter(user=self.applicant).exists())

    def test_request_deny(self):
        RequestFactory(team=self.team, user=self.applicant)
        self.client.force_login(self.member.user)
        response = self.client.post(
            reverse('denyrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.applicant.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.team.membership_set.filter(user=self.applicant).exists())
        self.assertFalse(self.team.request_set.filter(user=self.applicant).exists())

    def test_request_views_forbidden(self):
        self.client.logout()
        response = self.client.post(
            reverse('request', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.member.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('cancelrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.member.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.member.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('denyrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.member.id),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
