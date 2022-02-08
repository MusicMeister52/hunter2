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

from enumfields.admin import EnumFieldListFilter

from .forms import TeamForm
from . import models


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    form = TeamForm
    change_form_template = 'hunts/admin/change_team.html'
    ordering = ['at_event', 'name']
    list_display = ('the_name', 'at_event', 'role', 'member_count')
    list_display_links = ('the_name', )
    list_filter = (('role', EnumFieldListFilter),)
    search_fields = ('name', 'members__username')
    readonly_fields = ('token', )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('members', 'members')

    def member_count(self, team):
        return team.members.all().count()

    member_count.short_description = "Members"

    def the_name(self, team):
        return team.get_verbose_name()

    the_name.short_description = "Name"
    the_name.admin_order_field = "name"
