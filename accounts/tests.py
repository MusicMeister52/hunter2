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


from django.test import TestCase
from django.urls import reverse

from accounts.factories import UserInfoFactory, UserProfileFactory, UserFactory
from events.test import EventTestCase


class FactoryTests(TestCase):

    def test_user_info_factory_default_construction(self):
        UserInfoFactory.create()

    def test_user_profile_factory_default_construction(self):
        UserProfileFactory.create()

    def test_user_factory_default_construction(self):
        UserFactory.create()


class ProfileViewTests(EventTestCase):
    def test_load_profile_page(self):
        user = UserInfoFactory()
        response = self.client.get(reverse('profile', kwargs={
            'pk': user.id,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertIn(user.username.encode(response.charset), response.content)
