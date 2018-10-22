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
