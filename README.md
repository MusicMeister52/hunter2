Introduction
============

hunter2 is a web-application for running puzzle hunts. It provides a platform to host and view author-created puzzles,
monitor progression of teams, define automatic hints and unlockable clues and display statistics and graphs after the
hunt is over.

The app is written in python using the Django framework and set up to be quickly deployable with `docker-compose` on
either amd64 or ARM64 (v8) platforms.

Quick Evaluation Setup
===========

Ensure you have recent `docker-compose`, clone the repository, link the development compose file:
```shell
ln -s docker-compose.dev.yml docker-compose.yml
```

Build and launch containers:
```shell
make run
```

To create the database tables and base objects run the following:

```shell
docker-compose run --rm app migrate_schemas
docker-compose run --rm app setupsite
docker-compose run --rm app createsuperuser
docker-compose run --rm app createevent
```

Load an event page (such as [http://dev.hunter2.local:8080/hunt/](http://dev.hunter2.local:8080/hunt/)) and log in.

To access the full admin functionality, create a team and then use the Django admin interface
at `/admin/crud` (e.g. [http://dev.hunter2.local:8080/admin/crud/](http://dev.hunter2.local:8080/admin/crud/))
to change its role to "Admin". The normal hunt pages will then have an "Admin site" link at the top.

Documentation
=============

More complete documentation for hunt organisers and potential contributors is available at
[https://docs.hunter2.app](docs.hunter2.app)

Development
===========

Hunter 2 development happens on [our Discord](https://discord.gg/9jZEcr6FwT).
Please join us there if you want to get involved.

Copyright
=========
Hunter 2 is a platform for running online puzzle hunts. Further information can be found at https://www.hunter2.app/ including details of contributors.

Copyright (C) 2017-2021  The Hunter 2 contributors.

Hunter 2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

Hunter 2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Aferro General Public License for more details.

You should have received a copy of the GNU Aferro General Public License along with this program. If not, see <http://www.gnu.org/licenses/>.
