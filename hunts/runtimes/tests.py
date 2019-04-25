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


from django.test import TestCase, SimpleTestCase

from .iframe import IFrameRuntime
from .options import Case
from .regex import RegexRuntime
from .static import StaticRuntime
from .. import models

import re


class IFrameRuntimeTestCase(TestCase):
    def setUp(self):
        self.iframe_runtime = IFrameRuntime()

    def test_evaluate_no_param(self):
        iframe_url = r'https://example.com/'
        up_data = models.UserPuzzleData()
        response = self.iframe_runtime.evaluate(iframe_url, None, up_data, None, None)
        self.assertTrue(
            re.search(r'<iframe .* src="https://example.com/\?token=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"></iframe>', response)
        )

    def test_evaluate_with_param(self):
        iframe_url = r'https://example.com/?k=v'
        up_data = models.UserPuzzleData()
        response = self.iframe_runtime.evaluate(iframe_url, None, up_data, None, None)
        self.assertTrue(
            re.match(r'<iframe .* src="https://example.com/\?k=v&token=[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"></iframe>', response)
        )

    def test_validate_guess(self):
        iframe_url = r'https://example.com/'
        with self.assertRaises(NotImplementedError):
            self.iframe_runtime.validate_guess(iframe_url, "")


class RegexRuntimeTestCase(SimpleTestCase):
    def test_evaluate(self):
        regex_runtime = RegexRuntime(case_sensitive=False)
        regex_script = r'.*'
        with self.assertRaises(NotImplementedError):
            regex_runtime.evaluate(regex_script, None, None, None, None)

    def test_validate_guess(self):
        regex_runtime = RegexRuntime(case_sensitive=False)
        regex_script = r'Hello \w*!'
        guess = "Hello Planet!"
        result = regex_runtime.validate_guess(regex_script, guess)
        self.assertTrue(result)
        # Should be case insensitive
        guess = "hello Friend!"
        result = regex_runtime.validate_guess(regex_script, guess)
        self.assertTrue(result)
        guess = "Goodbye World!"
        result = regex_runtime.validate_guess(regex_script, guess)
        self.assertFalse(result)

    def test_case_sensitive_guess(self):
        regex_runtime = RegexRuntime(case_sensitive=True)
        regex_script = r'Hello \w*!'
        guess = "Hello casematching!"
        result = regex_runtime.validate_guess(regex_script, guess)
        self.assertTrue(result)
        guess = "hello nocapital!"
        result = regex_runtime.validate_guess(regex_script, guess)
        self.assertFalse(result)

    def test_evaluate_syntax_error_fails(self):
        regex_runtime = RegexRuntime(case_sensitive=False)
        regex_script = r'[]'
        with self.assertRaises(SyntaxError):
            regex_runtime.validate_guess(regex_script, "")


class StaticRuntimeTestCase(SimpleTestCase):
    def test_evaluate(self):
        static_runtime = StaticRuntime()
        static_script = '''Hello  World!'''
        result = static_runtime.evaluate(static_script, None, None, None, None)
        self.assertEqual(result, static_script)

    def test_validate_guess_no_strip(self):
        static_runtime = StaticRuntime(strip=False)
        static_script = 'Guess'
        guess = 'Guess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = 'Guess '
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)
        guess = 'G uess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)
        guess = 'G,uess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)
        guess = "incorrect guess"
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)

    def test_validate_guess_strip(self):
        static_runtime = StaticRuntime(case_handling=Case.FOLD)
        static_script = 'Guess'
        guess = 'Guess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = 'Guess '
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = 'G uess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)
        guess = 'G,uess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)
        guess = "incorrect guess"
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)

    def test_validate_guess_case_fold(self):
        static_runtime = StaticRuntime(case_handling=Case.FOLD)
        static_script = 'Guess'
        guess = 'Guess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = 'GUESS'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = 'gueß'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = "incorrect guess"
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)

    def test_validate_guess_case_lower(self):
        static_runtime = StaticRuntime(case_handling=Case.LOWER)
        static_script = 'Guess'
        guess = 'Guess'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = "GUESS"
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = 'gueß'
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)

    def test_validate_guess_case_none(self):
        static_runtime = StaticRuntime(case_handling=Case.NONE)
        static_script = 'Guess'
        guess = "Guess"
        result = static_runtime.validate_guess(static_script, guess)
        self.assertTrue(result)
        guess = "GUESS"
        result = static_runtime.validate_guess(static_script, guess)
        self.assertFalse(result)
