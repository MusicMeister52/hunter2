# Copyright (C) 2018-2021 The Hunter2 Contributors.
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


from django.db.models import Q
from django.urls import reverse

from hunts import models


def announcements(request):
    # Announcements are stored in tenant schemas. Some views won't have these in the search path.
    if request.tenant is None:
        return {}

    # Get all announcements, including puzzle specific announcements if present
    has_puzzle = hasattr(request, 'puzzle') and request.puzzle is not None

    if has_puzzle:
        current_announcements = models.Announcement.objects.filter(Q(puzzle__isnull=True) | Q(puzzle=request.puzzle))
    else:
        current_announcements = models.Announcement.objects.filter(puzzle__isnull=True)

    if request.user.is_authenticated:
        account_href = reverse('edit_profile')
        if request.tenant.seat_assignments and request.user.attendance_at(request.tenant).seat == '':
            no_seat = models.Announcement(
                id='no_seat',
                title='No Seat Set',
                message="You don't have a seat set at this event so we can find you if you're stuck. "
                        f"Please set your seat on the <a href={account_href}>account page</a>.",
                type=models.AnnouncementType.WARNING,
            )
            no_seat.special = True
            current_announcements = list(current_announcements) + [no_seat]
        if request.user.contact is None:
            no_contact = models.Announcement(
                id='no_contact',
                title='Can we contact you?',
                message="We'd like to contact you occasionally about this and future events. "
                        f"Please let us know whether we can on the <a href={account_href}>account page</a>.",
                type=models.AnnouncementType.INFO,
            )
            no_contact.special = True
            current_announcements = list(current_announcements) + [no_contact]

    return {
        'announcements': current_announcements
    }
