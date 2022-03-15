# Copyright (C) 2020-2021 The Hunter2 Contributors.
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


from .leaders import LeadersGenerator
from .progress import ProgressGenerator
from .puzzle_times import PuzzleTimesGenerator
from .top_guesses import TopGuessesGenerator
from .totals import TotalsGenerator
from .solve_time_distributions import SolveDistributionGenerator

# __all__ is iterated elsewhere, so it should only contain generator subclasses
__all__ = (
    LeadersGenerator,
    ProgressGenerator,
    TopGuessesGenerator,
    TotalsGenerator,
    PuzzleTimesGenerator,
    SolveDistributionGenerator,
)
