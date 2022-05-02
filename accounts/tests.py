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
from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from faker import Faker

from accounts.models import UserProfile
from events.factories import AttendanceFactory
from events.test import EventTestCase
from hunter2.models import Configuration
from teams.factories import TeamMemberFactory

from accounts.factories import UserFactory
from teams.models import TeamRole


class FactoryTests(TestCase):
    def test_user_factory_default_construction(self):
        UserFactory.create()


class ProfilePageTests(EventTestCase):
    def test_participant(self):
        user = TeamMemberFactory(team__role=TeamRole.PLAYER)
        team = user.team_at(self.tenant)
        AttendanceFactory(user=user, event=self.tenant)
        response = self.client.get(reverse('profile', kwargs={'uuid': user.uuid}))
        self.assertEqual(200, response.status_code)
        self.assertInHTML(
            f'<h2>Participant in</h2><ul><li>{team.name} @ {self.tenant.name}</li></ul>',
            response.content.decode('utf-8')
        )

    def test_admin(self):
        user = TeamMemberFactory(team__role=TeamRole.ADMIN)
        AttendanceFactory(user=user, event=self.tenant)
        response = self.client.get(reverse('profile', kwargs={'uuid': user.uuid}))
        self.assertEqual(200, response.status_code)
        self.assertInHTML(
            f'<h2>Admin at</h2><ul><li>{self.tenant.name}</li></ul>',
            response.content.decode('utf-8')
        )

    def test_author(self):
        user = TeamMemberFactory(team__role=TeamRole.AUTHOR)
        AttendanceFactory(user=user, event=self.tenant)
        response = self.client.get(reverse('profile', kwargs={'uuid': user.uuid}))
        self.assertEqual(200, response.status_code)
        self.assertInHTML(
            f'<h2>Author of</h2><ul><li>{self.tenant.name}</li></ul>',
            response.content.decode('utf-8')
        )


class AdminRegistrationTests(TestCase):
    def test_models_registered(self):
        models = apps.get_app_config('accounts').get_models()
        # Models which don't need to be registered due to being deprecated and retained only for old data migration
        exclude_models = (UserProfile, )
        for model in models:
            if model not in exclude_models:
                self.assertIsInstance(admin.site._registry[model], admin.ModelAdmin)


class SignupTests(TestCase):
    def setUp(self):
        self.fake = Faker()
        self.password = self.fake.password()

    def test_signup_saves_contact_choice(self):
        response = self.client.post(
            reverse('account_signup'),
            {
                'username': self.fake.user_name(),
                'email': self.fake.email(),
                'password1': self.password,
                'password2': self.password,
                'contact': 'False',  # False is more likely to be translated to None by accident than True
                'privacy': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)  # Should redirect back to where you were after signup
        User = get_user_model()
        self.assertIsNotNone(User.objects.get().contact)

    def test_signup_without_privacy(self):
        config = Configuration.get_solo()
        config.privacy_policy = self.fake.paragraph()
        config.save()
        response = self.client.post(
            reverse('account_signup'),
            {
                'username': self.fake.user_name(),
                'email': self.fake.email(),
                'password1': self.password,
                'password2': self.password,
                'contact': self.fake.boolean(),
                'privacy': 'off',
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_signup_with_missing_captcha(self):
        config = Configuration.get_solo()
        config.captcha_question = self.fake.paragraph()
        config.captcha_answer = self.fake.paragraph()
        config.save()
        response = self.client.post(
            reverse('account_signup'),
            {
                'username': self.fake.user_name(),
                'email': self.fake.email(),
                'password1': self.password,
                'password2': self.password,
                'contact': self.fake.boolean(),
            },
        )
        self.assertEqual(response.status_code, 200)  # 200, strangely, indicates the form was rejected
        self.assertInHTML('This field is required.', response.content.decode('utf-8'))

    def test_signup_with_wrong_captcha(self):
        config = Configuration.get_solo()
        config.captcha_question = self.fake.paragraph()
        config.captcha_answer = self.fake.paragraph()
        config.save()
        response = self.client.post(
            reverse('account_signup'),
            {
                'username': self.fake.user_name(),
                'email': self.fake.email(),
                'password1': self.password,
                'password2': self.password,
                'contact': self.fake.boolean(),
                'captcha': self.fake.paragraph(),
            },
        )
        self.assertEqual(response.status_code, 200)  # 200, strangely, indicates the form was rejected
        self.assertInHTML('You must correctly answer this question.', response.content.decode('utf-8'))

    def test_signup_with_right_captcha(self):
        config = Configuration.get_solo()
        config.captcha_question = self.fake.paragraph()
        config.captcha_answer = self.fake.paragraph().lower()
        config.save()
        response = self.client.post(
            reverse('account_signup'),
            {
                'username': self.fake.user_name(),
                'email': self.fake.email(),
                'password1': self.password,
                'password2': self.password,
                'contact': self.fake.boolean(),
                'captcha': config.captcha_answer.title(),
            },
        )
        self.assertEqual(response.status_code, 302)
