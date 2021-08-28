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

from string import Template

from django.db.models import BooleanField, ExpressionWrapper, Q
from django.urls import reverse

from .models import Icon
from .utils import wwwize
from . import settings


def site_theme(request):
    config = request.site_configuration
    files = config.files_map(request)
    return {
        'site_script': Template(config.script).safe_substitute(**files),
        'site_script_file': config.script_file.file.url if config.script_file else None,
        'site_style': Template(config.style).safe_substitute(**files),
        'site_style_file': config.style_file.file.url if config.style_file else None,
    }


def icons(request):
    # Fetching logic is entirely in a queryset and specifically not evaluated here,
    # such that if we hit the template fragment cache we do not perform the query
    queryset = Icon.objects.annotate(
        scalable=ExpressionWrapper(Q(size=0), output_field=BooleanField()),
    ).select_related('file').order_by('scalable', 'size')
    return {
        'icons': queryset,
    }


def login_url(request):
    return {
        'login_url': wwwize(reverse('account_login'), request),
    }


def sentry_dsn(request):
    dsn = settings.SENTRY_DSN
    if dsn:
        # If we have an old-style Sentry DSN with a password we need to strip it
        stripped = dsn._replace(netloc=f'{dsn.username}@{dsn.hostname}')
        dsn = stripped.geturl()
    return {
        'sentry_dsn': dsn,
    }


def privacy_policy(request):
    has_privacy_policy = request.site_configuration.privacy_policy != ''
    return {
        'footer_column_class': 'col-md-3' if has_privacy_policy else 'col-md-4',
        'has_privacy_policy': has_privacy_policy,
    }
