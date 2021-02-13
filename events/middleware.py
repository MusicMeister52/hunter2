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

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, ProgrammingError, connection
from django.utils.functional import LazyObject
from django_tenants.middleware import TenantMainMiddleware
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware

from accounts.models import UserInfo, UserProfile
from .models import Domain


class EventMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated and request.tenant is not None:
            UserProfile.objects.get_or_create(user=request.user)
            (user, _) = UserInfo.objects.get_or_create(user=request.user)
            user.attendance_set.get_or_create(
                user_info=request.user.info,
                event=request.tenant,
            )
        return


class TenantMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        try:
            super().process_request(request)
        except ProgrammingError as e:
            # Site has been accessed before initial migrate_schemas.
            raise DatabaseError("Initial schema migration has not been performed (see README.md)") from e
        except self.TENANT_NOT_FOUND_EXCEPTION:
            connection.set_schema_to_public()
            request.tenant = None
            if hasattr(settings, 'PUBLIC_SCHEMA_URLCONF'):
                request.urlconf = settings.PUBLIC_SCHEMA_URLCONF

            # This path bypasses the cache clear in the superclass
            ContentType.objects.clear_cache()


@database_sync_to_async
def get_tenant(scope):
    domain = scope['domain']
    try:
        return Domain.objects.get(domain=domain).tenant
    except Domain.DoesNotExist:
        return None


class TenantLazyObject(LazyObject):
    """
    Throw a more useful error message when scope['tenant'] is accessed before it's resolved
    """
    def _setup(self):
        raise ValueError("Accessing scope tenant before it is ready.")


class TenantWebsocketMiddleware(BaseMiddleware):
    def populate_scope(self, scope):
        """Put a tenant on the scope. Sets it to None if this can't be done so that the
        consumer can deal with the situation."""
        headers = dict(scope['headers'])

        if settings.USE_X_FORWARDED_HOST and b'x-forwarded-host' in headers:
            host_header = headers[b'x-forwarded-host']
        else:
            host_header = headers[b'host']

        try:
            host = host_header.decode('idna')
        except UnicodeDecodeError:
            scope['tenant'] = None
            return

        # urlparse will fail to parse an absolute URL without initial //
        scope['domain'] = urlparse('//' + host).hostname
        scope['tenant'] = TenantLazyObject()

    async def resolve_scope(self, scope):
        scope['tenant']._wrapped = await get_tenant(scope)
