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
from .options import Case


class StaticRuntime(AbstractRuntime):
    def __init__(self, case_handling=Case.LOWER, strip=True):
        self.case_handling = case_handling
        self.strip = strip

    def evaluate(self, script, team_puzzle_data, user_puzzle_data, team_data, user_data):
        return script

    def validate_guess(self, validator, guess):
        if self.strip:
            guess = guess.strip()
            validator = validator.strip()

        if self.case_handling == Case.FOLD:
            return validator.casefold() == guess.casefold()
        elif self.case_handling == Case.LOWER:
            return validator.lower() == guess.lower()
        else:
            return validator == guess
