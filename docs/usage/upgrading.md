# Upgrading

Upgrading is usually done by pulling images, running migrations, then updating the running containers, as follows:
```
docker-compose pull
docker-compose run --rm websocket migrate_schemas  # NOTE: use app rather than websocket here for the dev setup
docker-compose up -d
```

An `update.sh` script is provided to assist with this procedure, including reporting upgrade success/failure to Discord

## Versions Requiring Manual Intervention

### 2.0.0

Version 2.0.0 makes email confirmation mandatory by default.
This means that when upgrading to 2.0.0 you need to do one of the following two things:
- Disable email verification with the environment variable `H2_EMAIL_VERIFICATION=none`
- Ensure a working email sending service is configured using `H2_EMAIL_URL`

### 1.0.0

To upgrade to version 1.0.0 or later you need to upgrade from PostgreSQL 9.6 to 14 as follows:
1. BEFORE the upgrade, run `scripts/upgrade_1.0.0/pre-upgrade.sh`.
   This will remove DB exporter configuration from the database, shutdown hunter2,
   then create an upgraded copy of the database in a new volume.
2. Upgrade your installation as normal, but do not run `migrate_schemas`.
   Following the upgrade the app and/or websocket containers will not start up correctly.
3. (Optional, for production setups) Now is a good time to rotate your database passwords.
   The old ones had been stored in the database as MD5 whereas the new ones will be stored with SHA256.
4. Run `scripts/upgrade_1.0.0/post-upgrade.sh` to reset the passwords for all your DB users and
   reconfigure the DB exporter if you have a password for it configured.
5. Now run `migrate_schemas` to complete the upgrade.

### 0.5.0

To upgrade to version 0.5.0 or later you need to configure DB passwords in your `.env` file and migrate as follows:
```
# Stop all services
docker-compose down

# Migrate
docker-compose run --rm --entrypoint /bin/sh -v ${PWD}/backup:/mnt app
psql -h db -U postgres
CREATE DATABASE hunter2 WITH OWNER hunter2;
\c hunter2
REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM postgres;
GRANT ALL ON SCHEMA public TO hunter2;
ALTER SCHEMA public OWNER TO hunter2;
\q
pg_dump -h db -U postgres -O > /mnt/db.sql  # Dump DB without owner information
psql -h db -U hunter2 hunter2 < /mnt/db.sql  # Restore it using new owner
exit
docker-compose exec db /bin/sh
sh /docker-entrypoint-initdb.d/20-init-exporter.sh

# Secure
docker-compose exec db /bin/sh
psql -U postgres
\set postgres_password `echo "${POSTGRES_PASSWORD}"`
\q
sed -i 's/host all all all trust/host all all all md5/' /var/lib/postgresql/data/pg_hba.conf
exit
docker-compose restart db

# Cleanup
docker-compose exec db /bin/sh
psql -U postgres
### Do this for each of your events
# DROP SCHEMA event_slug CASCADE;
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
COMMENT ON SCHEMA public IS 'standard public schema';
GRANT ALL ON SCHEMA public TO PUBLIC;
GRANT ALL ON SCHEMA public TO postgres;

# Start services
docker-compose up -d
```

Finally you can remove the `POSTGRES_PASSWORD` from your `.env` file and store it safely for future use.
