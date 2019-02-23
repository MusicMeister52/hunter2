FROM registry.gitlab.com/rconan/docker-pipenv:2018.11.29-0 AS req_export

ARG DEVELOPMENT
COPY Pipfile Pipfile.lock /

RUN pipenv lock -r --keep-outdated > /requirements.txt
RUN [ -z ${DEVELOPMENT} ] || pipenv lock -d -r --keep-outdated >> /requirements.txt


# Construct a common base image for creating python wheels and the final image
FROM python:3.7.2-alpine3.8 AS runtime_base

RUN apk add --no-cache \
    lua5.2 \
    postgresql-client \
    postgresql-libs \
    imlib2

# Build image with all the pythong dependancies.
FROM runtime_base AS python_build

COPY --from=req_export /requirements.txt /usr/src/app/
WORKDIR /usr/src/app

RUN apk add --no-cache \
    gcc \
    git \
    linux-headers \
    lua5.2-dev \
    musl-dev \
    postgresql-dev
RUN pip install --no-deps -r requirements.txt


# Build all the required Lua components
FROM alpine:3.8 AS lua_build

COPY hunts/runtimes/lua/luarocks/config.lua /etc/luarocks/config-5.2.lua

RUN apk add --no-cache \
    curl \
    gcc \
    imlib2-dev \
    lua5.2-dev \
    luarocks5.2 \
    musl-dev
RUN luarocks-5.2 install lua-cjson 2.1.0-1
RUN luarocks-5.2 install lua-imlib2 dev-2


# Build the production webpack'ed assets
FROM node:11.9.0-alpine as webpack_build

WORKDIR /usr/src/app
COPY . .

RUN yarn install --frozen-lockfile
RUN ./node_modules/.bin/webpack --config webpack.prod.js


# Build the final image
FROM runtime_base

# Copy in the requried components from the previous build stages
COPY --from=python_build /usr/local/lib/python3.7/site-packages /usr/local/lib/python3.7/site-packages
COPY --from=lua_build /opt/hunter2 /opt/hunter2
COPY . /usr/src/app
COPY --from=webpack_build /usr/src/app/webpack-stats.json /usr/src/app/
COPY --from=webpack_build /usr/src/app/assets /usr/src/app/assets

WORKDIR /usr/src/app

# Setup user and required volumes
RUN addgroup -g 500 -S django \
 && adduser -h /usr/src/app -s /sbin/nologin -G django -S -u 500 django \
 && install -d -g django -o django /config /uploads/events /uploads/puzzles /uploads/solutions
USER django

VOLUME ["/config", "/uploads/events", "/uploads/puzzles", "/uploads/solutions"]

EXPOSE 8000

ENTRYPOINT ["python", "manage.py"]
CMD ["rundaphne", "--bind", "0.0.0.0"]
