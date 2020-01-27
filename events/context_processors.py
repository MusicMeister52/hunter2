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

from string import Template


def event_theme(request):
    context = {}
    if request.tenant:
        files = {f.slug: f.file.url for f in request.tenant.eventfile_set.filter(slug__isnull=False)}
        if request.tenant.theme.script:
            context['event_script'] = Template(request.tenant.theme.script).safe_substitute(**files)
        if request.tenant.theme.style:
            context['event_style'] = Template(request.tenant.theme.style).safe_substitute(**files)
    return context