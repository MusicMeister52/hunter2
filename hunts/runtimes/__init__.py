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


import inspect

from enumfields.enums import Enum, EnumMeta

from .iframe import IFrameRuntime
from .lua import LuaRuntime
from .regex import RegexRuntime
from .static import StaticRuntime


# Pattern copied from label handling in django-enumfields
class RuntimeMeta(EnumMeta):
    def __new__(mcs, name, bases, attrs):
        Types = attrs.get('Types')
        if Types is not None and inspect.isclass(Types):
            del attrs['Types']
            if hasattr(attrs, '_member_names'):
                attrs._member_names.remove('Types')

        obj = EnumMeta.__new__(mcs, name, bases, attrs)

        # Add the additional values to each Enum instance
        for m in obj:
            m.type = getattr(Types, m.name)

        return obj


class Runtime(Enum, metaclass=RuntimeMeta):
    IFRAME       = 'I'
    LUA          = 'L'
    REGEX        = 'R'
    STATIC       = 'S'

    class Labels:
        IFRAME       = 'IFrame'
        LUA          = 'Lua'
        REGEX        = 'Regex'
        STATIC       = 'Static'

    class Types:
        STATIC       = StaticRuntime
        REGEX        = RegexRuntime
        IFRAME       = IFrameRuntime
        LUA          = LuaRuntime

    def create(self, options):
        return self.type(**options)

    def is_printable(self):
        return self in (Runtime.REGEX, Runtime.STATIC)

    @property
    def grow_section(self):
        return self == Runtime.IFRAME
