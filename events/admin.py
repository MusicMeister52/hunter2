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


from django.contrib import admin
from django.db.models import Count
from rules.contrib.admin import ObjectPermissionsModelAdmin, ObjectPermissionsTabularInline
from . import models


class FileInline(ObjectPermissionsTabularInline):
    model = models.EventFile
    extra = 0


@admin.register(models.Event)
class EventAdmin(ObjectPermissionsModelAdmin):
    inlines = [
        FileInline,
    ]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            qs = qs.annotate(
                Count('teams', is_admin=True, members=request.user)
            ).filter(
                teams__count__gt=0
            )
        return qs


admin.site.register(models.Domain)
