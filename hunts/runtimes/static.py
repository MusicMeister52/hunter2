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


from .abstract import AbstractRuntime


class StaticRuntime(AbstractRuntime):
    def __init__(self, case_sensitive):
        self.case_sensitive = case_sensitive

    def evaluate(self, script, mode, team_puzzle_data, user_puzzle_data, team_data, user_data):
        return script

    def validate_guess(self, validator, guess):
        if self.case_sensitive:
            return validator == guess
        else:
            return validator.lower() == guess.lower()
