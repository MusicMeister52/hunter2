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


import logging
import os
import random
import tempfile
from io import StringIO

import builtins
import sys
from colour_runner.django_runner import ColourRunnerMixin
from django.contrib.sites.models import Site
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.test.runner import DiscoverRunner
from faker import Faker

from hunter2.management.commands import setupsite
from .utils import generate_secret_key, load_or_create_secret_key


class TestRunner(ColourRunnerMixin, DiscoverRunner):
    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        # Disable non-critial logging for test runs
        logging.disable(logging.CRITICAL)

        # Seed the random generators extracting the seed used
        # https://stackoverflow.com/a/5012617/393688
        default_seed = random.randrange(sys.maxsize)  # nosec random is fine for testing
        random_seed = os.getenv('H2_TEST_SEED', default_seed)
        random.seed(random_seed)
        Faker().seed(random_seed)
        print(f'Testing Seed: {random_seed}')

        return super().run_tests(test_labels, extra_tests, **kwargs)


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
        except SystemExit as e:
            self.fail("There are missing migrations:\n %s" % output.getvalue())


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
