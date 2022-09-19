# Copyright (C) 2022 The Hunter2 Contributors.
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
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from pytest_django.fixtures import SettingsWrapper
from pytest_django.lazy_django import skip_if_no_django


TEST_SCHEMA_NAME = "_pytest_schema"


@pytest.fixture(scope='session')
def session_settings():
    """Persist settings across all run tests."""
    skip_if_no_django()

    wrapper = SettingsWrapper()
    yield wrapper
    wrapper.finalize()


@pytest.fixture(scope='session')
def public_schema(django_db_setup, django_db_blocker):
    """ Initialize public schema. """

    with django_db_blocker.unblock():
        from django_tenants.utils import get_public_schema_name
        call_command("migrate_schemas", schema_name=get_public_schema_name(), interactive=False, verbosity=0)


@pytest.fixture(scope='session')
def test_schema(django_db_setup, django_db_blocker):
    """Initialize test schema."""

    from django_tenants.utils import schema_exists
    with django_db_blocker.unblock():
        if schema_exists(TEST_SCHEMA_NAME):
            call_command("migrate_schemas", schema_name=TEST_SCHEMA_NAME, interactive=False,
                         verbosity=0)
        else:
            from .models import Event
            Event(schema_name=TEST_SCHEMA_NAME).create_schema(verbosity=0)

    yield


@pytest.fixture
def event(db, test_schema, session_settings):
    """Main export of this module: provide an event object with the schema set up"""
    from django_tenants.utils import schema_context

    with schema_context("public"):
        from .models import Event

        # Note: this event is being created within the transaction that the `db` fixture provides, hence will be
        # removed after every test. However this does *not* remove the schema.
        event = Event(
            name="PyTest Event", schema_name=TEST_SCHEMA_NAME, current=True, end_date=timezone.now() + timedelta(days=5)
        )
        event.save()
        event.domains.create(domain="tenant.test.com")

    if event.get_primary_domain().domain not in session_settings.ALLOWED_HOSTS:
        session_settings.ALLOWED_HOSTS += [event.get_primary_domain().domain]

    connection.set_tenant(event)

    yield event

    connection.set_schema_to_public()
