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


from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.defaults import page_not_found, server_error, bad_request, permission_denied
from django.views.csrf import csrf_failure

from accounts.urls import urlpatterns as accounts_patterns

from . import settings
from .views import DefaultAdminView, DefaultIndexView, PrivacyView

urlpatterns = [
    path('admin/', DefaultAdminView.as_view(), name='admin'),
    path('', DefaultIndexView.as_view(), name='index'),
    path('privacy', PrivacyView.as_view(), name='privacy'),
] \
    + staticfiles_urlpatterns() \
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
    + accounts_patterns

if settings.DEBUG:

    # Http error code handlers (including CSRF validation)
    urlpatterns += [
        path('test/http/400/', bad_request, kwargs={'exception': Exception("Bad Request!")}),
        path('test/http/403/', permission_denied, kwargs={'exception': Exception("Permission Denied")}),
        path('test/http/403/csrf/', csrf_failure),
        path('test/http/404/', page_not_found, kwargs={'exception': Exception("Page not Found")}),
        path('test/http/500/', server_error),
    ]

    if settings.USE_SILK:  # nocover
        urlpatterns.append(
            path('silk/', include('silk.urls', namespace='silk')),
        )
