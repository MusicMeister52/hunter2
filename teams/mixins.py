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


from django.core.exceptions import ObjectDoesNotExist

from accounts.models import UserInfo, UserProfile
from .models import Membership, Team


class TeamMixin():
    def dispatch(self, request, *args, **kwargs):
        try:
            user = request.user.info
        except ObjectDoesNotExist:
            user = UserInfo(user=request.user)
            user.save()
        (profile, created) = UserProfile.objects.get_or_create(user=request.user)
        if created:
            profile.save()
        # TODO: May conflict with assignment of request.team in TeamMiddleware but shouldn't cause problems
        try:
            request.team = user.membership.team
        except UserInfo.membership.RelatedObjectDoesNotExist:
            request.team = Team(at_event=request.tenant)
            request.team.save()
            Membership(team=request.team, user=user).save()
        return super().dispatch(request, *args, **kwargs)
