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
import uuid

from django.apps import apps
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from unittest.mock import Mock

from accounts.factories import UserFactory
from events.factories import EventFactory, EventFileFactory
from events.test import EventAwareTestCase, EventTestCase
from hunter2.models import APIToken
from .middleware import TeamMiddleware
from .factories import TeamFactory, TeamMemberFactory
from .models import Team, TeamRole
from . import permissions


class FactoryTests(EventTestCase):

    def test_team_factory_default_construction(self):
        TeamFactory.create()

    def test_team_member_factory_default_construction(self):
        TeamMemberFactory.create()


class AdminRegistrationTests(TestCase):
    def test_models_registered(self):
        models = apps.get_app_config('teams').get_models()
        for model in models:
            self.assertIsInstance(admin.site._registry[model], admin.ModelAdmin)


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
        event = self.tenant
        event.max_team_size = 2
        event.save()
        team = TeamFactory(at_event=event)

        # Add 3 users to a team when that max is less than that.
        self.assertLess(event.max_team_size, 3)
        users = UserFactory.create_batch(3)

        with self.assertRaises(ValidationError):
            for user in users:
                team.members.add(user)

    def test_one_team_per_member_per_event(self):
        event = self.tenant
        teams = TeamFactory.create_batch(2, at_event=event)
        user = UserFactory()

        with self.assertRaises(ValidationError):
            teams[0].members.add(user)
            teams[1].members.add(user)


class TeamCreateTests(EventTestCase):
    def test_team_create(self):
        creator = UserFactory()
        team_template = TeamFactory.build()

        self.client.force_login(creator)
        response = self.client.post(
            reverse('create_team'),
            {
                'name': team_template.name,
            },
        )
        self.assertEqual(response.status_code, 302)
        team = Team.objects.get(name=team_template.name)
        self.assertTrue(creator in team.members.all())

    def test_team_middleware(self):
        request = Mock()
        request.tenant = self.tenant
        request.user = UserFactory()
        # Apply the middleware (ignore the result; we only care about what it does in the db)
        TeamMiddleware(Mock())(request)
        Team.objects.get(members=request.user)

    def test_automatic_creation(self):
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        Team.objects.get(members=user)


class InviteTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.team_admin = UserFactory()
        self.invitee = UserFactory()
        self.team = TeamFactory(at_event=self.event, members={self.team_admin})

        # Create an invite for the "invitee" user using the "team_admin" account.
        self.client.force_login(self.team_admin)
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.invitee.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_invite_invalid_uuid(self):
        # Send an invalid UUID request
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': '123',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Invalid User UUID')

    def test_invite_non_existent_uuid(self):
        # Send an valid UUID that doesn't exist
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': '01234567-89ab-cdef-0123-456789abcdef',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['message'], 'User does not exist')

    def test_invite_accept(self):
        self.client.force_login(self.invitee)
        response = self.client.post(
            reverse('acceptinvite', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.invitee in self.team.members.all())
        self.assertFalse(self.invitee in self.team.invites.all())

        # Now try to invite to a full team
        self.event.max_team_size = 2
        self.event.save()
        invitee2 = UserFactory()
        self.client.force_login(self.invitee)
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(invitee2.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(invitee2 in self.team.members.all())
        self.assertFalse(invitee2 in self.team.invites.all())

        # Now bypass the invitation mechanism to add an invite anyway and
        # check it can't be accepted
        self.team.invites.add(invitee2)
        self.client.force_login(invitee2)
        response = self.client.post(
            reverse('acceptinvite', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(invitee2 in self.team.members.all())
        # Finally check we cleaned up the invite after failing
        self.assertFalse(invitee2 in self.team.invites.all())

    def test_invite_cancel(self):
        # Send an invalid UUID request
        response = self.client.post(
            reverse('cancelinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': '123',
            }),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            reverse('cancelinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.invitee.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.invitee in self.team.members.all())
        self.assertFalse(self.invitee in self.team.invites.all())

    def test_invite_deny(self):
        self.client.force_login(self.invitee)
        response = self.client.post(
            reverse('denyinvite', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.invitee in self.team.members.all())
        self.assertFalse(self.invitee in self.team.invites.all())

    def test_invite_views_forbidden(self):
        self.client.logout()
        response = self.client.post(
            reverse('invite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('cancelinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('acceptinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('denyinvite', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


class RequestTests(EventTestCase):
    def setUp(self):
        self.event = self.tenant
        self.team_admin = UserFactory()
        self.applicant = UserFactory()
        self.team = TeamFactory(at_event=self.event, members={self.team_admin})

        # The "applicant" is requesting a place on "team".
        self.client.force_login(self.applicant)
        response = self.client.post(
            reverse('request', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

    def test_request_accept(self):
        self.client.force_login(self.team_admin)

        # Send an invalid UUID request
        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': '123',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['message'], 'Invalid User UUID')

        # Send a valid UUID that doesn't exist
        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': '01234567-89ab-cdef-0123-456789abcdef',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['message'], 'User does not exist')

        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.applicant.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.applicant in self.team.members.all())
        self.assertFalse(self.applicant in self.team.requests.all())

        # Now try to send a request to the full team
        self.event.max_team_size = 2
        self.event.save()
        applicant2 = UserFactory()
        self.client.force_login(applicant2)
        response = self.client.post(
            reverse('request', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(applicant2 in self.team.members.all())
        self.assertFalse(applicant2 in self.team.requests.all())

        # Now bypass the request mechanism to add a request anyway and
        # check it can't be accepted
        self.team.requests.add(applicant2)
        self.client.force_login(self.team_admin)
        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(applicant2.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(applicant2 in self.team.members.all())
        # Finally check we cleaned up the request after failing
        self.assertFalse(applicant2 in self.team.requests.all())

    def test_request_cancel(self):
        response = self.client.post(
            reverse('cancelrequest', kwargs={'team_id': self.team.id}),
            json.dumps({}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.applicant in self.team.members.all())
        self.assertFalse(self.applicant in self.team.requests.all())

    def test_request_deny(self):
        # Send an invalid UUID request
        response = self.client.post(
            reverse('denyrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': '123',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

        self.client.force_login(self.team_admin)
        response = self.client.post(
            reverse('denyrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.applicant.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.applicant in self.team.members.all())
        self.assertFalse(self.applicant in self.team.requests.all())

    def test_request_views_forbidden(self):
        self.client.logout()
        response = self.client.post(
            reverse('request', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('cancelrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('acceptrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        response = self.client.post(
            reverse('denyrequest', kwargs={'team_id': self.team.id}),
            json.dumps({
                'user': str(self.team_admin.uuid),
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)


class RulesTests(EventTestCase):
    def test_is_admin_for_event_true(self):
        user = TeamMemberFactory(team__role=TeamRole.ADMIN)
        self.assertTrue(permissions.is_admin_for_event.test(user, None))
        self.assertTrue(permissions.is_admin_for_event.test(user, self.tenant))

    def test_is_admin_for_event_false(self):
        user = TeamMemberFactory(team__role=TeamRole.PLAYER)
        self.assertFalse(permissions.is_admin_for_event.test(user, None))
        self.assertFalse(permissions.is_admin_for_event.test(user, self.tenant))

    def test_is_admin_for_event_with_no_team(self):
        user = UserFactory()
        self.assertFalse(permissions.is_admin_for_event.test(user, self.tenant))

    def test_is_admin_for_event_child_true(self):
        user = TeamMemberFactory(team__role=TeamRole.ADMIN)
        child = EventFileFactory()
        self.assertTrue(permissions.is_admin_for_event_child.test(user, None))
        self.assertTrue(permissions.is_admin_for_event_child.test(user, self.tenant))
        self.assertTrue(permissions.is_admin_for_event_child.test(user, child))

    def test_is_admin_for_event_child_false(self):
        user = TeamMemberFactory(team__role=TeamRole.PLAYER)
        child = EventFileFactory()
        self.assertFalse(permissions.is_admin_for_event_child.test(user, None))
        self.assertFalse(permissions.is_admin_for_event_child.test(user, self.tenant))
        self.assertFalse(permissions.is_admin_for_event_child.test(user, child))

    def test_is_admin_for_event_child_type_error(self):
        user = UserFactory()
        with self.assertRaises(TypeError):
            permissions.is_admin_for_event_child(user, "A string is not an event child")

    def test_is_admin_for_schema_event_true(self):
        user = TeamMemberFactory(team__role=TeamRole.ADMIN)
        self.assertTrue(permissions.is_admin_for_schema_event(user, None))

    def test_is_admin_for_schema_event_false(self):
        user = TeamMemberFactory(team__role=TeamRole.PLAYER)
        self.assertFalse(permissions.is_admin_for_schema_event(user, None))


class NoSchemaRulesTests(EventAwareTestCase):
    def test_is_admin_for_schema_event_no_event(self):
        event = EventFactory()
        event.activate()
        user = TeamMemberFactory(team__at_event=event, team__role=TeamRole.ADMIN)
        event.deactivate()
        self.assertFalse(permissions.is_admin_for_schema_event(user, None))


class TeamListTests(EventTestCase):
    def setUp(self):
        self.team = TeamFactory()
        self.player = UserFactory()
        self.player_team = TeamFactory(name='', members=self.player)
        self.url = reverse('team_list')
        self.api_token = APIToken()
        self.api_token.save()

    def test_negative_auth(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_json_list(self):
        response = self.client.get(self.url, HTTP_AUTHORIZATION=f'Bearer {self.api_token.token}')
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['items'][0]['id'], self.team.id)
        self.assertEqual(response_data['items'][0]['type'], 'team')
        self.assertEqual(response_data['items'][0]['name'], self.team.name)
        self.assertEqual(response_data['items'][1]['id'], self.player_team.id)
        self.assertEqual(response_data['items'][1]['type'], 'player')
        self.assertEqual(response_data['items'][1]['name'], self.player.username)

    def test_text_list(self):
        response = self.client.get(self.url, HTTP_ACCEPT='text/plain', HTTP_AUTHORIZATION=f'Bearer {self.api_token.token}')
        self.assertEqual(response.status_code, 200)
        response_data = response.content.decode('utf-8').split('\n')
        self.assertEqual(response_data[0], f'+{self.team.name}-')
        self.assertEqual(response_data[1], f'-{self.player.username}-')


class TeamInfoTests(EventTestCase):
    def test_no_api_token(self):
        team = TeamFactory()
        url = reverse('team_info', kwargs={
            'team_token': team.token,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_invalid_bearer_token(self):
        team = TeamFactory()
        url = reverse('team_info', kwargs={
            'team_token': team.token,
        })
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {uuid.uuid4()}')
        self.assertEqual(response.status_code, 401)

    def test_invalid_bearer_keyword(self):
        team = TeamFactory()
        url = reverse('team_info', kwargs={
            'team_token': team.token,
        })
        api_token = APIToken()
        api_token.save()
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bear {api_token.token}')
        self.assertEqual(response.status_code, 401)

    def test_short_authorization(self):
        team = TeamFactory()
        url = reverse('team_info', kwargs={
            'team_token': team.token,
        })
        api_token = APIToken()
        api_token.save()
        response = self.client.get(url, HTTP_AUTHORIZATION=f'{api_token.token}')
        self.assertEqual(response.status_code, 401)

    def test_long_authorization(self):
        team = TeamFactory()
        url = reverse('team_info', kwargs={
            'team_token': team.token,
        })
        api_token = APIToken()
        api_token.save()
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {api_token.token} bears')
        self.assertEqual(response.status_code, 401)

    def test_invalid_team_token(self):
        TeamFactory()
        url = reverse('team_info', kwargs={
            'team_token': uuid.uuid4(),
        })
        api_token = APIToken()
        api_token.save()
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {api_token.token}')
        self.assertEqual(response.status_code, 404)

    def test_team_found(self):
        team = TeamFactory()
        url = reverse('team_info', kwargs={
            'team_token': team.token,
        })
        api_token = APIToken()
        api_token.save()
        response = self.client.get(url, HTTP_AUTHORIZATION=f'Bearer {api_token.token}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['team']['name'], team.name)
