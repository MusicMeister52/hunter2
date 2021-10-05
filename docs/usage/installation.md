Setup
=====

Development Environment
-----------------------

### Prerequisites

Hunter 2 requires the following minimum versions to build:
| Dependency     | Version |
| -------------- | ------- |
| docker-engine  | 18.09   |
| docker-compose | 1.25.1  |

We need to export some variables to enable the build features we are using:
```shell
export COMPOSE_DOCKER_CLI_BUILD=1
export DOCKER_BUILDKIT=1
```

### Build and Launch the Application

Start from within a clone of the repository.

Link the development compose file:
```shell
ln -s docker-compose.dev.yml docker-compose.yml
```
This environment maps the local repo into the container and will dynamically reload code changes.

You will need to configure some hosts file entries, as the app uses DNS information to route to different events:
```shell
echo 127.0.0.1 hunter2.local www.hunter2.local dev.hunter2.local >> /etc/hosts
```
`dev.hunter2.local` is the default event subdomain. If you are working with more events, add more names here.

The quickest way to build and launch is:

```shell
make run
```

This can always be used to build any out of date images and restart everything that needs restarting.
You can always use `docker-compose` directly:

```shell
docker-compose build
docker-compose up -d
```

To create the database tables and base objects run the following:
```shell
docker-compose run --rm app migrate_schemas
docker-compose run --rm app setupsite
docker-compose run --rm app createsuperuser
docker-compose run --rm app createevent
```

Production Environment
----------------------

Link the production compose file:
```shell
ln -s docker-compose.prod.yml docker-compose.yml
```

Production environments require configuration of passwords for database users. Add the following to your `.env` file:
```
POSTGRES_PASSWORD=<password for DB superuser>
H2_DATABASE_PASSWORD=<password for hunter2 DB user>
H2_DB_EXPORTER_PASSWORD=<password for metrics exporter DB user>
```

You can generate random credentials for both these users with something like
```
echo "POSTGRES_PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 99 | head -n 1)" >> .env
echo "H2_DATABASE_PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 99 | head -n 1)" >> .env
echo "H2_DB_EXPORTER_PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 99 | head -n 1)" >> .env
```

Launch the containers and configure the database tables:
```shell
docker-compose up -d
docker-compose run --rm app migrate_schemas
```

You can now remove the `POSTGRES_PASSWORD` from your `.env` file and store it safely for future use.

To create the base objects run the following:
```shell
docker-compose run --rm app setupsite
docker-compose run --rm app createsuperuser
docker-compose run --rm app createevent
```

### Upgrading

Upgrading is usually done by pulling images, running migrations, then updating the running containers, as follows:
```
docker-compose pull
docker-compose run --rm app migrate_schemas
docker-compose up -d
```

An `update.sh` script is provided to assist with this procedure, including reporting upgrade success/failure to Discord

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
