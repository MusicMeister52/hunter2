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
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.test.cases import FastTenantTestCase
from django_tenants.test.client import TenantClient

from .factories import EventFactory, DomainFactory, ThemeFactory
from .models import Event


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
        self._flush_events()
        super()._fixture_teardown()


class EventTestCase(FastTenantTestCase):
    def _pre_setup(self):
        super()._pre_setup()

        self.client = TenantClient(self.tenant)

    @classmethod
    def setup_tenant(cls, tenant):
        theme = ThemeFactory()
        tenant.current = True
        tenant.end_date = timezone.now() + timedelta(days=5)
        tenant.name = 'Test Event'
        tenant.theme = theme


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
