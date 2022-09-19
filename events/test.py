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

import asyncio
from datetime import timedelta
from urllib.parse import unquote, urlparse

from channels.testing import WebsocketCommunicator, ApplicationCommunicator
from django.core.management import call_command
from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient

from .factories import EventFactory, DomainFactory
from .models import Event


TEST_SCHEMA_NAME = '_unittest_schema'


class EventAwareTestCase(TransactionTestCase):
    @staticmethod
    def _flush_events():
        for event in Event.objects.all():
            event.delete(force_drop=True)
            Event.deactivate()

    def _fixture_setup(self):
        self._flush_events()
        super()._fixture_setup()

    def _fixture_teardown(self):
        # Modify the default behaviour of TransactionTestCase to truncate both the test tenant schema and
        # the public schema, then leave the connection set to the public schema.
        for db_name in self._databases_names(include_mirrors=False):
            # Flush the database
            inhibit_post_migrate = (
                    self.available_apps is not None or
                    (   # Inhibit the post_migrate signal when using serialized
                        # rollback to avoid trying to recreate the serialized data.
                        self.serialized_rollback and
                        hasattr(connections[db_name], '_test_serialized_contents')
                    )
            )
            connection.set_tenant(Event(schema_name=TEST_SCHEMA_NAME))
            call_command(
                'flush',
                verbosity=0,
                interactive=False,
                database=db_name,
                reset_sequences=False,
                allow_cascade=self.available_apps is not None,
                inhibit_post_migrate=inhibit_post_migrate
            )
            connection.set_schema_to_public()
            # There are foreign keys from the non-public schemas to the public schema, so we must allow the truncate to
            # cascade. (This is not the default behaviour)) In the case where the only non-public schema is the one we
            # just deleted, this makes no difference beyond suppressing a SQL error. However, if another schema exists
            # then this is going to delete its corresponding row in the Event table in the public schema, which will
            # cascade to the tables in that other schema.
            call_command(
                'flush',
                verbosity=0,
                interactive=False,
                database=db_name,
                reset_sequences=False,
                allow_cascade=True,
                inhibit_post_migrate=inhibit_post_migrate
            )


class EventTestCase(FastTenantTestCase):
    def _pre_setup(self):
        super()._pre_setup()

        self.client = TenantClient(self.tenant)

    @classmethod
    def setup_tenant(cls, tenant):
        tenant.current = True
        tenant.end_date = timezone.now() + timedelta(days=5)
        tenant.name = 'Test Event'

    @classmethod
    def get_test_schema_name(cls):
        return TEST_SCHEMA_NAME


class ScopeOverrideCommunicator(WebsocketCommunicator):
    def __init__(self, application, path, scope=None, headers=None, subprotocols=None):
        if not isinstance(path, str):
            raise TypeError("Expected str, got {}".format(type(path)))
        if scope is None:
            scope = {}
        parsed = urlparse(path)
        self.scope = {
            "type": "websocket",
            "path": unquote(parsed.path),
            "query_string": parsed.query.encode("utf-8"),
            "headers": headers or [],
            "subprotocols": subprotocols or [],
        }
        self.scope.update(scope)
        ApplicationCommunicator.__init__(self, application, self.scope)


class AsyncEventTestCase(EventAwareTestCase):
    def setUp(self):
        self.tenant = EventFactory(max_team_size=2)
        self.domain = DomainFactory(tenant=self.tenant)
        self.tenant.activate()
        self.headers = [
            (b'origin', b'hunter2.local'),
            (b'host', self.domain.domain.encode('idna'))
        ]
        self.client = TenantClient(self.tenant)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Event.deactivate()
        try:
            cls.loop = asyncio.get_event_loop()
        except RuntimeError:
            raise RuntimeError('Could not create asyncio event loop; '
                               'something is messing with event loop policy which probably means'
                               'tests will not run as expected.')

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

    def get_communicator(self, app, url, scope=None):
        return ScopeOverrideCommunicator(app, url, scope, headers=self.headers)

    def receive_json(self, comm, msg='', no_fail=False):
        try:
            output = self.run_async(comm.receive_json_from)()
        except asyncio.TimeoutError:
            if no_fail:
                return {}
            else:
                self.fail(msg)
        return output

    def run_async(self, coro):
        async def wrapper(result, *args, **kwargs):
            try:
                r = await coro(*args, **kwargs)
            except Exception as e:
                result.set_exception(e)
            else:
                result.set_result(r)

        def inner(*args, **kwargs):
            result = asyncio.Future()
            if not self.loop.is_running():
                try:
                    self.loop.run_until_complete(wrapper(result, *args, **kwargs))
                finally:
                    pass
            else:
                raise RuntimeError('Event loop was already running. '
                                   'AsyncEventTestCase always stops the loop, '
                                   'so something else is using it in a way this is not designed for.')
            return result.result()

        return inner
