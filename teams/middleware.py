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


from .models import Team


class TeamMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.team = None

        if request.user.is_authenticated and request.tenant is not None:
            try:
                request.team = request.user.teams.get(at_event=request.tenant)
            except Team.DoesNotExist:
                request.team = Team(at_event=request.tenant)
                request.team.save()
                request.team.members.add(request.user)

        return self.get_response(request)
