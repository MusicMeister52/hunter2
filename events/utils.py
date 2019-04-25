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

from django.db.models import OuterRef, Subquery

from events.models import Attendance


def annotate_userinfo_queryset_with_seat(queryset, event):
    # This involves an ugly double join until UserProfile deprecation is complete
    return queryset.annotate(seat=Subquery(Attendance.objects.filter(user_info=OuterRef('pk'), event=event).values('seat')))


def annotate_userprofile_queryset_with_seat(queryset, event):
    # This involves an ugly double join until UserProfile deprecation is complete
    return queryset.annotate(seat=Subquery(Attendance.objects.filter(user_info__user=OuterRef('pk'), event=event).values('seat')))
