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
import importlib
import logging
import os
import random
import tempfile
import unittest
from datetime import timedelta, datetime
from datetime import timezone as dt_timezone
from io import StringIO

import builtins
import sys
from unittest import expectedFailure
from unittest.mock import patch

import freezegun
import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from faker import Faker
from gdpr_assist.upgrading import check_migrate_gdpr_anonymised
from xmlrunner.extra.djangotestrunner import XMLTestRunner

from teams.factories import TeamMemberFactory
from hunter2.management.commands import setupsite, anonymise
from events.test import EventTestCase
from .factories import FileFactory
from .utils import generate_secret_key, load_or_create_secret_key


class PytestTestRunner(XMLTestRunner):
    """Runs pytest to discover and run tests.

    Source: https://pytest-django.readthedocs.io/en/latest/faq.html#how-can-i-use-manage-py-test-with-pytest-django
    """

    def __init__(self, verbosity=1, failfast=False, keepdb=False, **kwargs):
        self.verbosity = verbosity
        self.failfast = failfast
        self.keepdb = keepdb

        super().__init__(**kwargs)

    @classmethod
    def add_arguments(cls, parser):
        super().add_arguments(parser)

    @staticmethod
    def translate_module_reference(label):
        """manage.py test expects labels of the form sub.module.Class.test_method. This translates this format to the
        pytest format of sub/module.py::Class::test_method"""

        # This logic is bad, but it's exactly what the django test runner does!

        parts = label.split('.')
        parts_left = parts[:]
        parts_right = []
        module = None
        # We don't know whether the last components are parts of the submodule path or methods or what, so we have to
        # do this by trial and error
        while parts_left:
            try:
                module_name = '.'.join(parts_left)
                module = importlib.import_module(module_name)
                break
            except ImportError:
                pass
            parts_right.insert(0, parts_left.pop())

        if module:
            return module.__file__ + '::' + '::'.join(parts_right)

        # if this doesn't work, maybe the unchanged label is supported after all; return it unchanged
        return label

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        """Run pytest and return the exitcode.

        It translates some of Django's test command option to pytest's.
        """
        import pytest

        argv = []
        if self.verbosity == 0:
            argv.append('--quiet')
        if self.verbosity == 2:
            argv.append('--verbose')
        if self.verbosity == 3:
            argv.append('-vv')
        if self.failfast:
            argv.append('--exitfirst')
        if self.keepdb:
            argv.append('--reuse-db')

        for label in test_labels:
            argv.append(self.translate_module_reference(label))

        # Disable non-critial logging for test runs
        logging.disable(logging.CRITICAL)

        # Seed the random generators extracting the seed used
        # https://stackoverflow.com/a/5012617/393688
        default_seed = random.randrange(sys.maxsize)  # nosec random is fine for testing
        random_seed = os.getenv('H2_TEST_SEED', default_seed)
        random.seed(random_seed)
        Faker.seed(random_seed)
        print(f'Testing Seed: {random_seed}')
        print("Run pytest directly (e.g. through the h2-test alias in h2tools.sh) for full access to pytest's command "
              "line arguments")

        return pytest.main(argv)


# Adapted from:
# https://github.com/django/django/blob/7588d7e439a5deb7f534bdeb2abe407b937e3c1a/tests/auth_tests/test_management.py
def mock_inputs(inputs):  # nocover
    """
    Decorator to temporarily replace input/getpass to allow interactive
    createsuperuser.
    """

    def inner(test_function):
        def wrap_input(*args):
            def mock_input(prompt):
                for key, value in inputs.items():
                    if key in prompt.lower():
                        return value
                return ""

            old_input = builtins.input
            builtins.input = mock_input
            try:
                test_function(*args)
            finally:
                builtins.input = old_input

        return wrap_input

    return inner


class MockTTY:
    """
    A fake stdin object that pretends to be a TTY to be used in conjunction
    with mock_inputs.
    """

    def isatty(self):  # nocover
        return True


@pytest.mark.usefixtures('db')
class TestFactories:
    def test_file_factory(self):
        FileFactory.create()


class MigrationsTests(TestCase):
    # Adapted for Python3 from:
    # http://tech.octopus.energy/news/2016/01/21/testing-for-missing-migrations-in-django.html
    @override_settings(MIGRATION_MODULES={})
    def test_for_missing_migrations(self):
        output = StringIO()
        try:
            call_command(
                'makemigrations',
                interactive=False,
                dry_run=True,
                check_changes=True,
                stdout=output
            )
        except SystemExit:
            self.fail("There are missing migrations:\n %s" % output.getvalue())

    # We silence the check that gdpr_assist runs on startup, but still want the things that check asserts to be true
    # for the app
    @override_settings(SILENCED_SYSTEM_CHECKS=())
    def test_gdpr_assist_check(self):
        self.assertEqual(check_migrate_gdpr_anonymised(None), [])


class SecretKeyGenerationTests(TestCase):
    def test_secret_key_length(self):
        secret_key = generate_secret_key()
        self.assertGreaterEqual(len(secret_key), 50)

    def test_subsequent_secret_keys_are_different(self):
        secret_key1 = generate_secret_key()
        secret_key2 = generate_secret_key()
        self.assertNotEqual(secret_key1, secret_key2)

    def test_write_generated_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            secrets_file = os.path.join(temp_dir, "secrets.ini")
            self.assertFalse(os.path.exists(secrets_file))
            load_or_create_secret_key(secrets_file)
            self.assertTrue(os.path.exists(secrets_file))

    def test_preserve_existing_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            secrets_file = os.path.join(temp_dir, "secrets.ini")
            self.assertFalse(os.path.exists(secrets_file))
            secret_key1 = load_or_create_secret_key(secrets_file)
            self.assertTrue(os.path.exists(secrets_file))
            secret_key2 = load_or_create_secret_key(secrets_file)
            self.assertEqual(secret_key1, secret_key2)


class SetupSiteManagementCommandTests(TestCase):
    TEST_SITE_NAME   = "Test Site"
    TEST_SITE_DOMAIN = "test-domain.local"

    def test_no_site_name_argument(self):
        output = StringIO()
        with self.assertRaisesMessage(CommandError, "You must use --name and --domain with --noinput."):
            call_command('setupsite', interactive=False, site_domain="custom-domain.local", stdout=output)

    def test_no_site_domain_argument(self):
        output = StringIO()
        with self.assertRaisesMessage(CommandError, "You must use --name and --domain with --noinput."):
            call_command('setupsite', interactive=False, site_name="Custom Site", stdout=output)

    def test_non_interactive_usage(self):
        output = StringIO()
        call_command(
            'setupsite',
            interactive=False,
            site_name=self.TEST_SITE_NAME,
            site_domain=self.TEST_SITE_DOMAIN,
            stdout=output
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, "Set site name as \"{}\" with domain \"{}\"".format(
            self.TEST_SITE_NAME,
            self.TEST_SITE_DOMAIN
        ))

        site = Site.objects.get()
        self.assertEqual(site.name,   self.TEST_SITE_NAME)
        self.assertEqual(site.domain, self.TEST_SITE_DOMAIN)

    @mock_inputs({
        'site name':   TEST_SITE_NAME,
        'site domain': TEST_SITE_DOMAIN
    })
    def test_interactive_usage(self):
        output = StringIO()
        call_command(
            'setupsite',
            interactive=True,
            stdout=output,
            stdin=MockTTY(),
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, "Set site name as \"{}\" with domain \"{}\"".format(
            self.TEST_SITE_NAME,
            self.TEST_SITE_DOMAIN
        ))
        site = Site.objects.get()
        self.assertEqual(site.name,   self.TEST_SITE_NAME)
        self.assertEqual(site.domain, self.TEST_SITE_DOMAIN)

    @mock_inputs({
        'site name':   "",
        'site domain': "",
    })
    def test_interactive_defaults_usage(self):
        output = StringIO()
        call_command(
            'setupsite',
            interactive=True,
            stdout=output,
            stdin=MockTTY(),
        )
        command_output = output.getvalue().strip()
        self.assertEqual(command_output, "Set site name as \"{}\" with domain \"{}\"".format(
            setupsite.Command.DEFAULT_SITE_NAME,
            setupsite.Command.DEFAULT_SITE_DOMAIN
        ))

        site = Site.objects.get()
        self.assertEqual(site.name,   setupsite.Command.DEFAULT_SITE_NAME)
        self.assertEqual(site.domain, setupsite.Command.DEFAULT_SITE_DOMAIN)

    def test_domain_validation(self):
        output = StringIO()
        test_domain = "+.,|!"
        with self.assertRaisesMessage(CommandError, "Domain name \"{}\" is not a valid domain name.".format(test_domain)):
            call_command(
                'setupsite',
                interactive=False,
                site_name=self.TEST_SITE_NAME,
                site_domain=test_domain,
                stdout=output
            )


class AnonymisationCommandTests(EventTestCase):
    def setUp(self):
        # When a Daylight Savings Time boundary occurs during the window in the relative time specification
        # there's an ambiguity whether "a day ago" means the same local time on the previous calendar day
        # or 24 hours earlier.
        # We're choosing to interpret it as the same local time on the previous calendar day and accordingly
        # need to craft the cutoff carefully.
        now = timezone.localtime()
        tz = now.tzinfo
        self.cutoff = tz.localize(now.replace(tzinfo=None) - timedelta(days=1))
        self.user_before = TeamMemberFactory(
            username='person1',
            email='someone@somewhere.com',
            last_login=self.cutoff - timedelta(minutes=1),
            picture='https://imagesite.com/an_image.jpg',
            contact=True,
        )
        SocialAccount(user=self.user_before, uid=1).save()
        EmailAddress(user=self.user_before, email=self.user_before.email).save()
        self.before_pk = self.user_before.pk
        self.user_after = TeamMemberFactory(last_login=self.cutoff + timedelta(minutes=1))
        self.after_username = self.user_after.username
        self.after_email = self.user_after.email
        self.after_picture = self.user_after.picture
        self.after_contact = self.user_after.contact
        SocialAccount(user=self.user_after, uid=2).save()
        EmailAddress(user=self.user_after, email=self.user_after.email).save()

    def test_no_site_name_argument(self):
        output = StringIO()
        with self.assertRaisesMessage(CommandError, "Error: the following arguments are required"):
            call_command('anonymise', interactive=False, stdout=output)

    def test_no_cancels(self):
        output = StringIO()
        with patch('builtins.input') as mock_input:
            mock_input.return_value = "no"
            call_command('anonymise', self.cutoff.isoformat(), stdout=output)
            mock_input.assert_called_once_with(
                f'Anonymise 1 users who last logged in before {self.cutoff.isoformat(" ", "seconds")}? (yes/no) '
            )
        output = output.getvalue().strip()

        self.assertIn('Aborting', output)

        self.user_before.refresh_from_db()
        self.user_after.refresh_from_db()

        self.assertEqual(self.user_before.username, 'person1')
        self.assertEqual(self.user_before.email, 'someone@somewhere.com')
        self.assertEqual(self.user_before.picture, 'https://imagesite.com/an_image.jpg')
        self.assertEqual(self.user_before.contact, True)

        self.assertEqual(self.user_after.username, self.after_username)
        self.assertEqual(self.user_after.email, self.after_email)
        self.assertEqual(self.user_after.picture, self.after_picture)
        self.assertEqual(self.user_after.contact, self.after_contact)

    def test_usage(self):
        output = StringIO()
        call_command('anonymise', self.cutoff.isoformat(), yes=True, stdout=output)
        output = output.getvalue().strip()

        self.assertIn('1 users who last logged in before', output)
        self.assertIn('Done', output)

        self.usage_assertions()

    def test_usage_interactive(self):
        output = StringIO()
        with patch('builtins.input') as mock_input:
            mock_input.return_value = "yes"
            call_command('anonymise', self.cutoff.isoformat(), stdout=output)
            mock_input.assert_called_once_with(
                f'Anonymise 1 users who last logged in before {self.cutoff.isoformat(" ", "seconds")}? (yes/no) '
            )
        output = output.getvalue().strip()

        self.assertIn('Done', output)

        self.usage_assertions()

    def test_usage_relative(self):
        output = StringIO()
        call_command('anonymise', "1 day ago", yes=True, stdout=output)
        output = output.getvalue().strip()

        self.assertIn('1 users who last logged in before', output)
        self.assertIn('Done', output)

        self.usage_assertions()

    def usage_assertions(self):
        self.user_before.refresh_from_db()
        self.user_after.refresh_from_db()

        self.assertEqual(self.user_before.username, f'{self.before_pk}')
        self.assertEqual(self.user_before.email, f'{self.before_pk}@anon.example.com')
        self.assertEqual(self.user_before.picture, '')
        self.assertEqual(self.user_before.contact, False)
        self.assertEqual(SocialAccount.objects.filter(user=self.user_before).count(), 0)
        self.assertEqual(EmailAddress.objects.filter(user=self.user_before).count(), 0)
        self.assertEqual(self.user_after.username, self.after_username)
        self.assertEqual(self.user_after.email, self.after_email)
        self.assertEqual(self.user_after.picture, self.after_picture)
        self.assertEqual(self.user_after.contact, self.after_contact)
        self.assertEqual(SocialAccount.objects.filter(user=self.user_after).count(), 1)
        self.assertEqual(EmailAddress.objects.filter(user=self.user_after).count(), 1)


class AnonymisationMethodTests(EventTestCase):
    def test_parse_date_parses_isodate(self):
        self.assertEqual(
            anonymise.Command.parse_date('2020-01-02T18:03:04+01:00'),
            datetime(2020, 1, 2, 18, 3, 4, tzinfo=dt_timezone(timedelta(hours=1)))
        )

    def test_parse_date_parses_relative_date(self):
        with freezegun.freeze_time(datetime(2020, 1, 2, tzinfo=dt_timezone(timedelta(hours=-1)))):
            self.assertEqual(
                anonymise.Command.parse_date('one year ago'),
                datetime(2019, 1, 2, tzinfo=dt_timezone(timedelta(hours=-1)))
            )

    def test_parse_date_parses_ambiguous_date(self):
        self.assertEqual(
            anonymise.Command.parse_date('01/02/03'),
            datetime(2003, 2, 1, tzinfo=dt_timezone(timedelta(hours=0)))
        )

    # TODO see https://github.com/scrapinghub/dateparser/issues/412
    @expectedFailure
    def test_parse_date_parses_ambiguous_date_year_first(self):
        self.assertEqual(
            anonymise.Command.parse_date('2001/02/03'),
            datetime(2001, 2, 3, tzinfo=dt_timezone(timedelta(hours=0)))
        )

    def test_get_confirmation(self):
        cmd = anonymise.Command()
        with unittest.mock.patch.object(builtins, 'input') as mock_input:
            mock_input.return_value = 'yes'
            self.assertTrue(cmd.get_confirmation(False, range(5), datetime.fromisoformat('2020-01-02 00:00')))
            mock_input.assert_called_once_with(
                'Anonymise 5 users who last logged in before 2020-01-02 00:00:00? (yes/no) '
            )

        with unittest.mock.patch.object(builtins, 'input') as mock_input:
            mock_input.return_value = 'no'
            self.assertFalse(cmd.get_confirmation(False, range(3), datetime.fromisoformat('2020-01-04 00:00')))
            mock_input.assert_called_once_with(
                'Anonymise 3 users who last logged in before 2020-01-04 00:00:00? (yes/no) '
            )
