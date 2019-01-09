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

from .forms import MembershipForm
from . import models


@admin.register(models.Membership)
class MembershipAdmin(admin.ModelAdmin):
    form = MembershipForm
    readonly_fields = (
        'user',
    )


class InviteInline(admin.TabularInline):
    model = models.Invite
    extra = 0


class MembershipInline(admin.TabularInline):
    model = models.Membership
    readonly_fields = (
        'user',
    )
    can_delete = False
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


class RequestInline(admin.TabularInline):
    model = models.Request
    extra = 0


@admin.register(models.Team)
class TeamAdmin(admin.ModelAdmin):
    inlines = (MembershipInline, InviteInline, RequestInline)
    ordering = ('at_event', 'name')
    list_display = ('the_name', 'at_event', 'is_admin', 'member_count')
    list_display_links = ('the_name', )

#    class Media:
#        css = { "all": ("teams/css/hide_admin_original.css",) }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('membership_set', 'membership_set__user')

    def member_count(self, team):
        return team.membership_set.all().count()

    member_count.short_description = "Members"

    def the_name(self, team):
        return team.get_verbose_name()

    the_name.short_description = "Name"
    the_name.admin_order_field = "name"
