# vim: set fileencoding=utf-8 :
from .external import ExternalRuntime
from .lua import LuaRuntime
from .regex import RegexRuntime
from .static import StaticRuntime


class RuntimesRegistry(object):
    EXTERNAL = 'E'
    LUA      = 'L'
    REGEX    = 'R'
    STATIC   = 'S'

    RUNTIME_CHOICES = (
        (EXTERNAL, 'External Runtime'),
        (LUA,      'Lua Runtime'),
        (REGEX,    'Regex Runtime'),
        (STATIC,   'Static Runtime'),
    )

    REGISTERED_RUNTIMES = {
        EXTERNAL: ExternalRuntime(),
        LUA:      LuaRuntime(),
        REGEX:    RegexRuntime(),
        STATIC:   StaticRuntime(),
    }

    @staticmethod
    def evaluate(runtime, script, team_puzzle_data, user_puzzle_data, team_data, user_data):
        return RuntimesRegistry.REGISTERED_RUNTIMES[runtime].evaluate(
            script,
            team_puzzle_data=team_puzzle_data,
            user_puzzle_data=user_puzzle_data,
            team_data=team_data,
            user_data=user_data,
        )

    @staticmethod
    def validate_guess(runtime, script, guess, team_puzzle_data, team_data):
        return RuntimesRegistry.REGISTERED_RUNTIMES[runtime].validate_guess(
            script,
            guess,
            team_puzzle_data=team_puzzle_data,
            team_data=team_data,
        )
