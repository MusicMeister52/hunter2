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


import os
import sys

from ..abstract import AbstractRuntime
from ..exceptions import RuntimeExecutionError, RuntimeExecutionTimeExceededError, RuntimeMemoryExceededError, RuntimeSandboxViolationError

# TODO: Replace this with proper DLFCN support in the docker python version
orig_dlflags = sys.getdlopenflags()
sys.setdlopenflags(258)
import lupa  # noqa: E402
sys.setdlopenflags(orig_dlflags)


class LuaRuntime(AbstractRuntime):
    DEFAULT_INSTRUCTION_LIMIT = 1e6  # Instructions
    DEFAULT_MEMORY_LIMIT      = 200  # KB

    ERROR_INSTRUCTION_LIMIT_EXCEEDED = "ERROR_INSTRUCTION_LIMIT_EXCEEDED"
    ERROR_MEMORY_LIMIT_EXCEEDED      = "ERROR_MEMORY_LIMIT_EXCEEDED"
    ERROR_SANDBOX_VIOLATION          = "ERROR_SANDBOX_VIOLATION"

    def __init__(self):
        pass

    def check_script(self, script):
        try:
            # Use the sandbox engine with a *very* restrictive limit which will prevent anything meaningful happening.
            # TODO: look at a way to restrict this completely.
            self._sandbox_run(script, instruction_limit=10)
        except RuntimeExecutionTimeExceededError:
            return True

    def evaluate(self, script, team_puzzle_data, user_puzzle_data, team_data, user_data):
        return_values = self._sandbox_run(script, {
            "team_puzzle_data": team_puzzle_data,
            "user_puzzle_data": user_puzzle_data,
            "team_data":        team_data,
            "user_data":        user_data,
        })

        if len(return_values) == 0:
            raise RuntimeExecutionError("Lua script did not return a value")

        return return_values[0]

    def validate_guess(self, validator, guess):
        return_values = self._sandbox_run(validator, {
            "guess":            guess,
        })

        if len(return_values) == 0:
            raise RuntimeExecutionError("Lua script did not return a value")

        return return_values[0]

    def _create_lua_runtime(self):
        # noinspection PyArgumentList
        lua = lupa.LuaRuntime(
            register_eval=False,
            register_builtins=False,
            unpack_returned_tuples=True,
        )

        # Ensure the local is consistent and ignore system Lua paths
        lua.execute("assert(os.setlocale('C'))")
        lua.globals().package.path  = ';'.join([
            os.path.join(os.path.dirname(__file__), "?.lua"),
            "/opt/hunter2/share/lua/5.2/?.lua",
        ])

        # TODO: Support cross platform libraries
        lua.globals().package.cpath = ';'.join([
            "/opt/hunter2/lib/lua/5.2/?.so",
        ])

        return lua

    def _sandbox_run(
            self,
            lua_script,
            parameters=None,
            instruction_limit=DEFAULT_INSTRUCTION_LIMIT,
            memory_limit=DEFAULT_MEMORY_LIMIT):
        lua = self._create_lua_runtime()

        # Load the sandbox Lua module
        sandbox = lua.require('sandbox')

        # Load parameters into the sandbox
        if parameters is not None:
            for key, value in parameters.items():
                if sandbox.env[key] is not None:
                    raise RuntimeExecutionError("Passed parameter '{}' overrides sandbox environment".format(key))
                else:
                    sandbox.env[key] = value

        # Enable instruction and memory limits
        sandbox.enable_limits(instruction_limit, memory_limit)

        # The 'result' object here can be either a bool or a tuple depending on
        # the result of the Lua function, the following results are possible:
        #  - True:           script succeeded but returned nothing
        #  - (True, ...):    script succeeded with return values
        #  - (False, error): script raised an error during execution
        #  - (None, error):  script syntax loading error
        try:
            result = sandbox.run(lua_script)
            # If just a bool, return the empty result for success
            if isinstance(result, bool) and result is True:
                return []

            # Check result of executing the Lua script
            if result[0] is not True:
                exit_status, error = result

                if exit_status is None:
                    raise SyntaxError(error)

                if exit_status is False:
                    if str(error).endswith(self.ERROR_INSTRUCTION_LIMIT_EXCEEDED):
                        raise RuntimeExecutionTimeExceededError()
                    elif str(error).endswith(self.ERROR_MEMORY_LIMIT_EXCEEDED):
                        raise RuntimeMemoryExceededError()
                    elif str(error).endswith(self.ERROR_SANDBOX_VIOLATION):
                        raise RuntimeSandboxViolationError(str(error).replace(" " + self.ERROR_SANDBOX_VIOLATION, ""))
                    else:
                        raise RuntimeExecutionError(error)
            else:
                # Expand the return values to a list and return
                exit_status, *return_values = result
                return return_values

        except lupa.LuaError as error:
            # An error has occurred in the sandbox runtime itself
            raise RuntimeExecutionError("Sandbox") from error
