# vim: set fileencoding=utf-8 :
from unittest import TestCase, expectedFailure

from parameterized import parameterized

from .. import RuntimeExecutionError, RuntimeExecutionTimeExceededError, RuntimeMemoryExceededError
from . import LuaRuntime


class LuaRuntimeTestCase(TestCase):
    def test_evaluate(self):
        lua_runtime = LuaRuntime()
        lua_script = '''return "Hello World"'''
        result = lua_runtime.evaluate(lua_script, None, None, None, None)
        self.assertEqual(result, "Hello World")

    def test_evaluate_requires_return_value(self):
        lua_runtime = LuaRuntime()
        lua_script = ''''''
        with self.assertRaises(RuntimeExecutionError):
            lua_runtime.evaluate(lua_script, None, None, None, None)

    # TODO: Implement passing of the guess object into the runtime
    @expectedFailure
    def test_validate_guess(self):
        lua_runtime = LuaRuntime()
        lua_script = '''return (guess == 100 + 100)'''
        guess = "200"
        result = lua_runtime.validate_guess(lua_script, guess, None, None)
        self.assertTrue(result, "Guess was correct, but did not return true")

    def test_validate_guess_requires_return_value(self):
        lua_runtime = LuaRuntime()
        lua_script = ''''''
        with self.assertRaises(RuntimeExecutionError):
            lua_runtime.validate_guess(lua_script, None, None, None)

    def test_evaluate_syntax_error_fails(self):
        lua_runtime = LuaRuntime()
        lua_script = '''@'''
        with self.assertRaises(SyntaxError):
            lua_runtime.evaluate(lua_script, None, None, None, None)

    def test_evaluate_error_fails(self):
        lua_runtime = LuaRuntime()
        lua_script = '''error("error_message")'''
        with self.assertRaises(RuntimeExecutionError) as context:
            lua_runtime.evaluate(lua_script, None, None, None, None)
            self.assertEqual(context.exception.message, "error_message")


class LuaSandboxTestCase(TestCase):
    # Functions that we do not want to expose to our sandbox
    PROTECTED_FUNCTIONS = [
        'collectgarbage',
        'dofile',
        'load',
        'loadfile',
        'coroutine',
        'debug',
        'io',
        'os.date',
        'os.execute',
        'os.exit',
        'os.getenv',
        'os.remove',
        'os.rename',
        'os.setlocale',
        'os.tmpname',
        'package',
        'string.dump',
    ]

    @parameterized.expand(PROTECTED_FUNCTIONS)
    def test_lua_sandbox_disabled(self, unsafe_function):
        lua_runtime = LuaRuntime()
        lua_script = '''return {} == nil'''.format(unsafe_function)
        result = lua_runtime._sandbox_run(lua_script)[0]
        self.assertTrue(result, "Lua function {} is accessible in sandbox".format(unsafe_function))

    def test_lua_sandbox_instruction_limit(self):
        lua_runtime = LuaRuntime()
        lua_script = '''for i=1,100000 do print("Hello!") end'''
        with self.assertRaises(RuntimeExecutionTimeExceededError):
            lua_runtime._sandbox_run(lua_script)

    def test_lua_sandbox_memory_limit(self):
        lua_runtime = LuaRuntime()
        lua_script = '''t = {} for i=1,10000 do t[i] = i end'''
        with self.assertRaises(RuntimeMemoryExceededError):
            lua_runtime._sandbox_run(lua_script)
