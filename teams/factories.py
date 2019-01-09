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


from collections.abc import Iterable
import warnings

import factory
from faker import Faker

from accounts.factories import UserInfoFactory, UserProfileFactory
from events import factories
from .models import Membership


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'teams.Team'

    name = factory.Sequence(lambda n: f'{n}{Faker().color_name()}')
    at_event = factory.SubFactory(factories.EventFactory)
    is_admin = False

    @factory.post_generation
    def members(self, create, extracted, **kwargs):
        warnings.warn('Implicit member creation is deprecated. Use MembershipFactory instead.', DeprecationWarning)
        if not create:
            return

        if extracted:
            for member in (extracted if isinstance(extracted, Iterable) else (extracted,)):
                Membership(team=self, user=member.user.info).save()


class MembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'teams.Membership'

    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserInfoFactory)


class InviteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'teams.Invite'

    team = factory.SubFactory(TeamFactory)
    by = factory.SubFactory(UserInfoFactory)
    user = factory.SubFactory(UserInfoFactory)


class RequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'teams.Request'

    team = factory.SubFactory(TeamFactory)
    user = factory.SubFactory(UserInfoFactory)


class TeamMemberFactory(UserProfileFactory):
    class Meta:
        exclude = ('team',)

    team = factory.RelatedFactory(TeamFactory, 'members')
