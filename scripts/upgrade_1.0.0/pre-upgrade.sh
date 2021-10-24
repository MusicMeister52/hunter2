#!/usr/bin/env bash
# Copyright (C) 2021 The Hunter2 Contributors.
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

set -euo pipefail
IFS=$'\n\t'

# This script is intended to be run before upgrading to 1.0.0
# It will remove the DB exporter stuff from the DB then shutdown hunter2 and migrate the DB data to a new volume in PostgreSQL 14.x format

docker-compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres <<EOSQL
    DO \$\$ BEGIN
        DROP SCHEMA IF EXISTS postgres_exporter CASCADE;
        DROP EXTENSION IF EXISTS pg_stat_statements CASCADE;
        IF EXISTS (
            SELECT * FROM pg_roles WHERE rolname = 'postgres_exporter'
        ) THEN
            DROP OWNED BY postgres_exporter;
            DROP ROLE postgres_exporter;
        END IF;
    END \$\$;
EOSQL

docker-compose down
docker run --rm \
    -v pg_upgrade_logs:/var/lib/postgresql:z \
    -v hunter2_db:/var/lib/postgresql/9.6/data:z \
    -v hunter2_db14:/var/lib/postgresql/14/data:z \
    tianon/postgres-upgrade:9.6-to-14 -v
docker run --rm -v hunter2_db14:/mnt:z alpine:3.14 /bin/sh -c 'echo "host all all all scram-sha-256" >> /mnt/pg_hba.conf'
