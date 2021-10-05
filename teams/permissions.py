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

from django.db import connections
from django_tenants.utils import get_tenant_database_alias, get_tenant_model
import rules


@rules.predicate
def is_admin_for_schema_event(user, obj):
    connection = connections[get_tenant_database_alias()]
    TenantModel = get_tenant_model()
    try:
        event = TenantModel.objects.get(schema_name=connection.schema_name)
    except TenantModel.DoesNotExist:
        return False
    return is_admin_for_event.test(user, event)


@rules.predicate
def is_admin_for_event(user, event):
    from teams.models import Team

    if event is None:
        return is_admin_for_schema_event.test(user, event)
    try:
        return user.profile.team_at(event).is_admin
    except (Team.DoesNotExist, AttributeError):
        return False


@rules.predicate
def is_admin_for_event_child(user, obj):
    from events.models import Event
    if obj is None:  # If we have no object we're checking globally for the event specified by the active schema
        return is_admin_for_event.test(user, None)

    # We either have an Event or something with a direct foreign key to an Event named event
    try:
        event = obj if isinstance(obj, Event) else obj.event
    except AttributeError as e:
        raise TypeError('is_admin_for_event_child must be called with an Event or a type with a foreign key to it called "event"') from e

    return is_admin_for_event.test(user, event)


rules.add_perm('events', is_admin_for_event)

# Admin teams cannot create or delete events, only update and view
rules.add_perm('events.change_event', is_admin_for_event)
rules.add_perm('events.view_event', is_admin_for_event)
rules.add_perm('events.add_eventfile', is_admin_for_event_child)
rules.add_perm('events.change_eventfile', is_admin_for_event_child)
rules.add_perm('events.delete_eventfile', is_admin_for_event_child)
rules.add_perm('events.view_eventfile', is_admin_for_event_child)


rules.add_perm('teams', is_admin_for_schema_event)

rules.add_perm('teams.add_team', is_admin_for_schema_event)
rules.add_perm('teams.change_team', is_admin_for_schema_event)
rules.add_perm('teams.delete_team', is_admin_for_schema_event)
rules.add_perm('teams.view_team', is_admin_for_schema_event)
