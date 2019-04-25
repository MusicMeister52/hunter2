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


import re

from .abstract import AbstractRuntime


class RegexRuntime(AbstractRuntime):
    flags = 0

    def __init__(self, case_sensitive=False):
        self.flags = 0 if case_sensitive else re.IGNORECASE

    def check_script(self, script):
        try:
            re.compile(script, flags=self.flags)
        except re.error as error:
            raise SyntaxError(error) from error

    def evaluate(self, script, team_puzzle_data, user_puzzle_data, team_data, user_data):
        raise NotImplementedError("RegexRuntime can not be used for static evaluation")

    def validate_guess(self, validator, guess):
        try:
            return re.fullmatch(validator, guess, flags=self.flags)
        except re.error as error:
            raise SyntaxError(error) from error
