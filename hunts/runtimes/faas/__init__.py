# Copyright (C) 2019 The Hunter2 Contributors.
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

import json

from ..abstract import AbstractRuntime
from .lambda_runtime import AwsLambdaRuntime


EXECUTION_RUNTIMES = {
    'aws-lambda': AwsLambdaRuntime,
}


class FaasRuntime(AbstractRuntime):
    def _make_runtime(self, function_metadata):
        return EXECUTION_RUNTIMES[function_metadata['execution_runtime']]()

    def check_script(self, script):
        try:
            function_metadata = json.loads(script)
            runtime = self._make_runtime(function_metadata)
            return runtime.check_metadata(function_metadata)
        except:
            return False

    def call(self, script, state_dict):
        function_metadata = json.loads(script)
        runtime = self._make_runtime(function_metadata)
        return runtime.call(function_metadata, state_dict)

    def evaluate(self, script, mode, team_puzzle_data, user_puzzle_data, team_data, user_data):
        state_dict = {
            'event': mode,
            'team_puzzle_data': team_puzzle_data.data,
            'user_puzzle_data': user_puzzle_data.data,
            'team_data': team_data.data,
            'user_data': user_data.data,
        }
        function_result = self.call(script, state_dict)
        datum = [
            (team_puzzle_data, function_result.get('team_puzzle_data')),
            (user_puzzle_data, function_result.get('user_puzzle_data')),
            (team_data, function_result.get('team_data')),
            (user_data, function_result.get('user_data')),
        ]
        for original_data, new_data in datum:
            if new_data is not None:
                original_data.data = new_data
        return function_result['body']

    def validate_guess(self, script, guess):
        state_dict = {
            'event': 'guess',
            'guess': guess,
        }
        function_result = self.call(script, state_dict)
        return function_result['is_correct']
