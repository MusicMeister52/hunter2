#!/bin/sh
set -euo pipefail

[ -n "${H2_DATABASE_PASSWORD:-}" ] || return 0

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" <<-EOSQL
    CREATE USER hunter2;
    ALTER USER hunter2 WITH PASSWORD '${H2_DATABASE_PASSWORD}';
    CREATE DATABASE hunter2 OWNER hunter2;
EOSQL

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" --dbname hunter2 <<-EOSQL
    GRANT ALL ON SCHEMA public TO hunter2;
    REVOKE ALL ON SCHEMA public FROM postgres;
    REVOKE ALL ON SCHEMA public FROM PUBLIC;
EOSQL
