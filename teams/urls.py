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


from django.urls import include, path
from . import views

teampatterns = [
    path('', views.TeamView.as_view(), name='team'),
    path('invite', views.Invite.as_view(), name='invite'),
    path('cancelinvite', views.CancelInvite.as_view(), name='cancelinvite'),
    path('acceptinvite', views.AcceptInvite.as_view(), name='acceptinvite'),
    path('denyinvite', views.DenyInvite.as_view(), name='denyinvite'),
    path('request', views.Request.as_view(), name='request'),
    path('cancelrequest', views.CancelRequest.as_view(), name='cancelrequest'),
    path('acceptrequest', views.AcceptRequest.as_view(), name='acceptrequest'),
    path('denyrequest', views.DenyRequest.as_view(), name='denyrequest'),
]

eventpatterns = [
    path('team/', views.ManageTeamView.as_view(), name='manage_team'),
    path('team/create', views.CreateTeamView.as_view(), name='create_team'),
    path('team/<int:team_id>/', include(teampatterns), name='team'),
    path('teaminfo/<uuid:team_token>', views.TeamInfoView.as_view(), name='team_info'),
    path('teamlist/', views.TeamListView.as_view(), name='team_list'),
]

urlpatterns = [
    path('hunt/', include(eventpatterns)),
    path('team_autocomplete', views.TeamAutoComplete.as_view(), name='team_autocomplete'),
]
