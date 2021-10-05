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

import rules

from teams.permissions import is_admin_for_schema_event


def set_all_perms_for_model(app, model, predicate):
    rules.add_perm(f'{app}.add_{model}', predicate)
    rules.add_perm(f'{app}.change_{model}', predicate)
    rules.add_perm(f'{app}.delete_{model}', predicate)
    rules.add_perm(f'{app}.view_{model}', predicate)


rules.add_perm('hunts', is_admin_for_schema_event)

set_all_perms_for_model('hunts', 'announcement', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'answer', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'episode', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'headstart', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'hint', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'puzzle', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'puzzlefile', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'solutionfile', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'teamdata', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'teampuzzledata', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'unlock', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'unlockanswer', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'userdata', is_admin_for_schema_event)
set_all_perms_for_model('hunts', 'userpuzzledata', is_admin_for_schema_event)
