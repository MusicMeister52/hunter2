# Copyright (C) 2018-2022 The Hunter2 Contributors.
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


from django.urls import include, path
from . import views

urlpatterns = [
    path('accounts/password/change/', views.PasswordChangeView.as_view(), name='account_change_password'),
    path('accounts/', include('allauth.urls')),
    path('profile/<uuid:uuid>', views.ProfileView.as_view(), name='profile'),
    path('profile/edit', views.EditProfileView.as_view(), name='edit_profile'),
    path('user_autocomplete/', views.UserAutoComplete.as_view(), name='user_autocomplete'),
]
