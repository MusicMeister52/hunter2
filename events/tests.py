# Copyright (C) 2018-2021 The Hunter2 Contributors.
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


from io import StringIO
from unittest.case import expectedFailure

from django.apps import apps
from django.contrib import admin
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse

from events.factories import AttendanceFactory, EventFactory, EventFileFactory
from events.models import Event, EventFile
from hunter2.tests import MockTTY, mock_inputs
from . import factories
from .management.commands import createevent
from .test import EventAwareTestCase, EventTestCase


class FactoryTests(EventTestCase):

    def test_event_file_factory_default_construction(self):
        EventFileFactory.create()

    def test_attendance_factory_default_construction(self):
        AttendanceFactory.create()

    def test_event_factory_errors_in_testcase(self):
        with self.assertRaises(AssertionError):
            EventFactory.create()


class AdminRegistrationTests(TestCase):
    def test_models_registered(self):
        models = apps.get_app_config('events').get_models()
        # Models which don't need to be directly registered due to being managed by inlines
        inline_models = (EventFile, )
        for model in models:
            if model not in inline_models:
                self.assertIsInstance(admin.site._registry[model], admin.ModelAdmin)


class EventRulesTests(EventAwareTestCase):

    def test_only_one_current_event(self):
        # Ensure that we only have one event set as current
        factories.EventFactory(current=True)
        event = factories.EventFactory(current=True)
        self.assertEqual(len(Event.objects.filter(current=True)), 1, "More than one event is set as current")
        self.assertEqual(Event.objects.get(current=True), event, "Last added event is not current")

    @expectedFailure  # TODO: Currently fails but non-critical
    def test_only_remaining_event_is_current(self):
        # Ensure that we only have one event set as current after deleting the current test
        event1 = factories.EventFactory(current=True)
        event2 = factories.EventFactory(current=True)
        event2.delete()
        self.assertEqual(len(Event.objects.filter(current=True)), 1, "No current event set")
        self.assertEqual(Event.objects.get(current=True), event1, "Only remaining event is not current")

    def test_current_by_default_event(self):
        # If we only have one event is should be set as current by default, regardless if set as current
        event = factories.EventFactory(current=False)
        self.assertTrue(event.current, "Only event is not set as current")


class CreateEventManagementCommandTests(EventAwareTestCase):
    TEST_EVENT_NAME = "Custom Event"
    TEST_SUBDOMAIN = 'custom'
    TEST_EVENT_END_DATE = "Monday at 18:00"
    INVALID_END_DATE = "18:00 on the second Sunday after Pentecost"

    def test_no_event_name_argument(self):
        output = StringIO()
        with self.assertRaisesMessage(CommandError, "You must use --event, --subdomain and --enddate with --noinput."):
            call_command(
                'createevent',
                interactive=False,
                subdomain=self.TEST_SUBDOMAIN,
                end_date=self.TEST_EVENT_END_DATE,
                stdout=output
            )

    def test_no_end_date_argument(self):
        output = StringIO()
        with self.assertRaisesMessage(CommandError, "You must use --event, --subdomain and --enddate with --noinput."):
            call_command(
                'createevent',
                interactive=False,
                subdomain=self.TEST_SUBDOMAIN,
                event_name="Test Event",
                stdout=output
            )

    def test_invalid_date(self):
        output = StringIO()
        with self.assertRaisesMessage(CommandError, "End date is not a valid date."):
            call_command(
                'createevent',
                interactive=False,
                event_name=self.TEST_EVENT_NAME,
                subdomain=self.TEST_SUBDOMAIN,
                end_date=self.INVALID_END_DATE,
                stdout=output
            )

    def test_non_interactive_usage(self):
        output = StringIO()
        call_command(
            'createevent',
            interactive=False,
            event_name=self.TEST_EVENT_NAME,
            subdomain=self.TEST_SUBDOMAIN,
            end_date=self.TEST_EVENT_END_DATE,
            stdout=output
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, f'Created current event "{self.TEST_EVENT_NAME}"')

        event = Event.objects.get(name=self.TEST_EVENT_NAME, current=True)
        self.assertIsNotNone(event)

    @mock_inputs({
        'event': TEST_EVENT_NAME,
        'subdomain': TEST_SUBDOMAIN,
    })
    def test_interactive_usage(self):
        output = StringIO()
        call_command(
            'createevent',
            interactive=True,
            stdout=output,
            stdin=MockTTY(),
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, f'Created current event "{self.TEST_EVENT_NAME}"')

        event = Event.objects.get(name=self.TEST_EVENT_NAME, current=True)
        self.assertIsNotNone(event)

    @mock_inputs({
        'end date': "",
        'event': "",
        'subdomain': "",
    })
    def test_default_interactive_usage(self):
        output = StringIO()
        call_command(
            'createevent',
            interactive=True,
            stdout=output,
            stdin=MockTTY(),
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, f'Created current event "{createevent.Command.DEFAULT_EVENT_NAME}"')

        event = Event.objects.get(name=createevent.Command.DEFAULT_EVENT_NAME, current=True)
        self.assertIsNotNone(event)

    def test_only_one_current_event(self):
        output = StringIO()
        new_name = self.TEST_EVENT_NAME + "1"
        call_command(
            'createevent',
            interactive=False,
            event_name=new_name,
            subdomain=self.TEST_SUBDOMAIN + "1",
            end_date=self.TEST_EVENT_END_DATE,
            stdout=output
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, f'Created current event "{new_name}"')

        output = StringIO()
        new_name = self.TEST_EVENT_NAME + "2"
        call_command(
            'createevent',
            interactive=False,
            event_name=new_name,
            subdomain=self.TEST_SUBDOMAIN + "2",
            end_date=self.TEST_EVENT_END_DATE,
            stdout=output
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, f'Created current event "{new_name}"')

        self.assertGreater(Event.objects.all().count(), 1)
        self.assertEqual(Event.objects.filter(current=True).count(), 1, "More than a single event with current set as True")


class EventContentTests(EventTestCase):
    def test_can_load_about(self):
        self.tenant.about_text = '__test__'
        self.tenant.save()
        url = reverse('about')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '__test__')
