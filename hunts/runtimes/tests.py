# vim: set fileencoding=utf-8 :
from unittest import TestCase

from .external import ExternalRuntime
from .regex import RegexRuntime
from .static import StaticRuntime

import requests


class ExternalRuntimeTestCase(TestCase):
    def test_connection(self):
        external_runtime = ExternalRuntime()
        external_uri = r'http://example:8080/content'
        r = requests.post(external_uri, json={'team_id': 1})
        r.raise_for_status()



class RegexRuntimeTestCase(TestCase):
    def test_evaluate(self):
        regex_runtime = RegexRuntime()
        regex_script = r'.*'
        with self.assertRaises(NotImplementedError):
            regex_runtime.evaluate(regex_script, None, None, None, None)

    def test_validate_guess(self):
        regex_runtime = RegexRuntime()
        regex_script = r'Hello \w*!'
        guess1 = "Hello Planet!"
        result = regex_runtime.validate_guess(regex_script, guess1, None, None)
        self.assertTrue(result)
        guess2 = "Goodbye World!"
        result = regex_runtime.validate_guess(regex_script, guess2, None, None)
        self.assertFalse(result)

    def test_evaluate_syntax_error_fails(self):
        regex_runtime = RegexRuntime()
        regex_script = r'[]'
        with self.assertRaises(SyntaxError):
            regex_runtime.validate_guess(regex_script, "", None, None)


class StaticRuntimeTestCase(TestCase):
    def test_evaluate(self):
        static_runtime = StaticRuntime()
        static_script = '''Hello  World!'''
        result = static_runtime.evaluate(static_script, None, None, None, None)
        self.assertEqual(result, static_script)

    def test_validate_guess(self):
        static_runtime = StaticRuntime()
        static_script = '''answer'''
        guess1 = "answer"
        result = static_runtime.validate_guess(static_script, guess1, None, None)
        self.assertTrue(result)
        guess2 = "incorrect answer"
        result = static_runtime.validate_guess(static_script, guess2, None, None)
        self.assertFalse(result)
