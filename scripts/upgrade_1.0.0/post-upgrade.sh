#!/usr/bin/env bash
#
# Copyright (C) 2021-2022 The Hunter2 Contributors.
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
#

set -euo pipefail
IFS=$'\n\t'

# This script is intended to be run after upgrading to 1.0.0
# It resets DB credentials for all users it can, then reconfigures the DB exporter setup

docker-compose exec -T db /bin/sh <<-'EOF'
    [[ -n "${H2_DATABASE_PASSWORD}" ]] && psql -v ON_ERROR_STOP=1 -U postgres -c "ALTER ROLE hunter2 WITH PASSWORD '${H2_DATABASE_PASSWORD}';"
    [[ -n "${POSTGRES_PASSWORD}" ]] && psql -v ON_ERROR_STOP=1 -U postgres -c "ALTER ROLE postgres WITH PASSWORD '${POSTGRES_PASSWORD}';"
    sh /docker-entrypoint-initdb.d/20-init-exporter.sh
EOF
