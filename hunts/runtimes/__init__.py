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


from hunts.runtimes.automation import AutomationRuntime
from hunts.runtimes.iframe import IFrameRuntime
from hunts.runtimes.lua import LuaRuntime
from hunts.runtimes.regex import RegexRuntime
from hunts.runtimes.static import StaticRuntime

AUTOMATION   = 'A'
CASED_REGEX  = 'r'
CASED_STATIC = 's'
IFRAME       = 'I'
LUA          = 'L'
REGEX        = 'R'
STATIC       = 'S'

RUNTIME_CHOICES = (
    (STATIC,       'Static'),
    (CASED_STATIC, 'Case Sensitive Static'),
    (REGEX,        'Regex'),
    (CASED_REGEX,  'Case Sensitive Regex'),
    (IFRAME,       'IFrame'),
    (LUA,          'Lua'),
    (AUTOMATION,   'Automatic Completion'),
)


class Runtimes:
    runtimes = {
        CASED_REGEX:  (RegexRuntime, {'case_sensitive': True}),
        CASED_STATIC: (StaticRuntime, {'case_sensitive': True}),
        IFRAME:       (IFrameRuntime, {}),
        LUA:          (LuaRuntime, {}),
        REGEX:        (RegexRuntime, {'case_sensitive': False}),
        STATIC:       (StaticRuntime, {'case_sensitive': False}),
        AUTOMATION:   (AutomationRuntime, {}),
    }

    def __getitem__(self, key):
        # Return an instantiated copy of the requested runtime
        entry = self.runtimes[key]
        return entry[0](**entry[1])


runtimes = Runtimes()
