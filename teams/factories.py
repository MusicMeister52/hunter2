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

import factory
from faker import Faker

from accounts.factories import UserFactory
from events.factories import activated_event

from .models import TeamRole


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'teams.Team'

    name = factory.Sequence(lambda n: f'{n}{Faker().color_name()}')
    at_event = factory.LazyFunction(activated_event)
    role = TeamRole.PLAYER

    @factory.post_generation
    def members(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for member in (extracted if isinstance(extracted, Iterable) else (extracted,)):
                self.members.add(member)


class TeamMemberFactory(UserFactory):
    class Meta:
        exclude = ('team',)

    team = factory.RelatedFactory(TeamFactory, 'members')
