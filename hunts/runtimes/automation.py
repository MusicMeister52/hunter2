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


import uuid

from .abstract import AbstractRuntime


class AutomationRuntime(AbstractRuntime):
    def check_script(self, script):
        try:
            return str(uuid.UUID(script))  # Try to normalise the UUID string
        except ValueError:
            return str(uuid.uuid4())  # Generate a new one if it's invalid

    def evaluate(self, script, team_puzzle_data, user_puzzle_data, team_data, user_data):
        raise NotImplementedError("AutomationRuntime can not be used for static evaluation")

    def validate_guess(self, validator, guess):
        return False
