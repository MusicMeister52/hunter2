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

import configparser
import logging
import random
import traceback

from django.conf import settings
from urllib.parse import urlsplit, urlunsplit


def generate_secret_key():
    return ''.join([random.SystemRandom().choice('abcdefghijklmnopqrstuvwxyz0123456789_') for i in range(50)])


def load_or_create_secret_key(secrets_file):
    config = configparser.ConfigParser()
    config.read(secrets_file)

    if config.has_option('Secrets', 'django_secret_key'):
        secret_key = config.get('Secrets', 'django_secret_key')
    else:
        secret_key = generate_secret_key()

        # Write the configuration to the secrets file.
        config.add_section('Secrets')
        config.set('Secrets', 'django_secret_key', secret_key)
        with open(secrets_file, 'w+') as configfile:
            config.write(configfile)

    return secret_key


def wwwize(url, request):
    absolute_uri = request.build_absolute_uri(url)
    logging.debug(absolute_uri)
    components = urlsplit(absolute_uri)
    domain = f'www.{settings.BASE_DOMAIN}'
    try:
        port = components.netloc.split(':')[1]
        netloc = f'{domain}:{port}'
    except IndexError:
        netloc = domain

    return urlunsplit(components[:1] + (netloc,) + components[2:])


class StackInfoLoggingMixin:
    """This mixin adds a stack trace of the log record afterwards

    The assumption is that this will cause a lot of spam in logs, so stack
    traces are limited to source files within the app base dir.
    Facility is provided to skip spammy log lines.

    Attributes:
        bad: iterable of str: if any of these strings appears in the message,
            don't emit it
        bad_stack: iterable of str: if any of these strings appear in any of the
            traceback entries, don't emit the message
        emit_empty_stack: bool: whether to emit the log message if the stack is empty
    """
    bad_msg = ()
    bad_stack = ()
    emit_empty_stack = False
    logged = 0

    def get_stack(self, record):
        # The last three stack entries will be this method, self.emit: strip them off.
        stack = [str(s) for s in traceback.format_stack()][:-2]
        stack = [s for s in stack if settings.BASE_DIR in s]
        return stack

    def should_emit(self, record, stack):
        args = str(record.args)
        if not any(b in args for b in self.bad_msg):
            if not stack and not self.emit_empty_stack:
                # Don't emit the log message at all
                return False
            for b in self.bad_stack:
                if any(b in s for s in stack):
                    return False
            # Log lines from tests are probably uninteresting
            if '/tests/' in stack[-1] or 'tests.py' in stack[-1]:
                return False
        else:
            return False

        return True

    def emit(self, record):
        stack = self.get_stack(record)
        if not self.should_emit(record, stack):
            return

        self.logged += 1
        if stack:
            record.msg = f'logged {self.logged:03d} {record.msg} ***{self.terminator}{"".join(stack)}'
        else:
            record.msg = f'logged {self.logged:03d} {record.msg}'
        super().emit(record)


class DBLogHandler(StackInfoLoggingMixin, logging.StreamHandler):
    # These are spammy, but the list is not complete; it may be necessary
    # to extend it for a particular application.
    bad_msg = (
        'SET search_path',
        'SHOW search_path',
        'django_migrations',
        'content_type',
        'conname',
        'pg_catalog',
        'ALTER',
        'CREATE',
        'SEQUENCE',
        'CONSTRAINT',
    )
    bad_stack = (
        'Factory',
        '/migrations/',
    )
