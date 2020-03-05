#!/bin/sh
set -euo pipefail

[ -z "${H2_DATABASE_PASSWORD:-}" ] || psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<-EOSQL
    CREATE USER hunter2;
    CREATE DATABASE hunter2 OWNER hunter2;
    ALTER USER hunter2 WITH PASSWORD '${H2_DATABASE_PASSWORD}';
EOSQL
