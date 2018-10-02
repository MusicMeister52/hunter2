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


from allauth.account.views import logout as allauth_logout
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views.defaults import page_not_found, server_error, bad_request, permission_denied
from django.views.csrf import csrf_failure

from accounts.urls import urlpatterns as accounts_patterns
from hunts.urls import urlpatterns as hunts_patterns
from teams.urls import urlpatterns as teams_patterns

from . import settings

# Wrap the admin login page with login_required so that it goes through allauth login.
admin.site.login = login_required(admin.site.login)
# Replace the admin logout view with the allauth logout view.
# Unfortunately the admin UI makes a GET so we can't avoid the confirmation page.
admin.site.logout = allauth_logout

urlpatterns = [
    path('accounts/', include('allauth.urls')),
    path('jet/', include('jet.urls', 'jet')),
    path('jet/dashboard/', include('jet.dashboard.urls', 'jet-dashboard')),
    path('admin/', admin.site.urls),
    path('nested_admin/', include('nested_admin.urls')),
] \
    + staticfiles_urlpatterns() \
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
    + accounts_patterns \
    + hunts_patterns \
    + teams_patterns

if settings.DEBUG:

    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

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
