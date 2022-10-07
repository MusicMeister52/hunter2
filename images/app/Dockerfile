# Construct a common base image for creating python wheels and the final image
FROM python:3.10.7-alpine3.15@sha256:8cdc31f3a7f640537b38a7ad8ee5d154c2963a066e82c2a2a6fa6f3cc7fbfcba AS runtime_base

RUN --mount=type=cache,target=/var/cache/apk apk add \
    libxml2 \
    libxslt \
    lua5.2 \
    postgresql-client \
    postgresql-libs \
    imlib2

# Setup user
RUN addgroup -g 500 -S hunter2 \
 && adduser -h /opt/hunter2 -s /sbin/nologin -G hunter2 -S -u 500 hunter2
WORKDIR /opt/hunter2/src


# Build image with all the python dependencies.
FROM runtime_base AS python_build

RUN --mount=type=cache,target=/var/cache/apk apk add \
    gcc \
    git \
    libffi-dev \
    lua5.2-dev \
    musl-dev

# Suppress pip version warning, we're keeping the version from the docker base image
ARG PIP_DISABLE_PIP_VERSION_CHECK=1

ENV PATH "/root/.local/bin:${PATH}"
RUN wget -q -O - https://raw.githubusercontent.com/python-poetry/install.python-poetry.org/9b64f71d730d7be00e204b96a095b38af9e909e3/install-poetry.py | python3 - --version 1.2.0 \
 && poetry config virtualenvs.create false \
 && python -m venv /opt/hunter2/venv

ARG dev_flag=" --only main"
COPY poetry.lock poetry.toml pyproject.toml /opt/hunter2/src/
RUN --mount=type=cache,target=/root/.cache/pip \
    . /opt/hunter2/venv/bin/activate \
 && poetry install${dev_flag} --no-root --no-interaction --verbose


# Build all the required Lua components
FROM alpine:3.15.4@sha256:4edbd2beb5f78b1014028f4fbb99f3237d9561100b6881aabbf5acce2c4f9454 AS lua_build

COPY hunts/runtimes/lua/luarocks/config.lua /etc/luarocks/config-5.2.lua

RUN  --mount=type=cache,target=/var/cache/apk apk add \
    curl \
    gcc \
    imlib2-dev \
    lua5.2-dev \
    luarocks5.2 \
    musl-dev
RUN --mount=type=cache,target=/root/.cache/luarocks \
    luarocks-5.2 install lua-cjson 2.1.0-1
RUN --mount=type=cache,target=/root/.cache/luarocks \
    luarocks-5.2 install lua-imlib2 dev-2


# Build the production webpack'ed assets
FROM node:18.10.0-alpine3.15@sha256:96f0b877b028b0b0ab7ba296eb0cee5558fe4920b4cb267c9125324c0c20e312 as webpack_build

WORKDIR /opt/hunter2/src

COPY package.json yarn.lock /opt/hunter2/src/
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile
COPY . .
RUN --mount=type=cache,target=/var/cache/babel-loader "$(yarn bin webpack)" --config webpack.prod.js


# Build the final image
FROM runtime_base

# Copy in the requried components from the previous build stages
COPY --from=lua_build /opt/hunter2 /opt/hunter2
COPY --from=python_build /opt/hunter2/venv /opt/hunter2/venv
COPY --from=webpack_build /opt/hunter2/assets /opt/hunter2/assets
COPY --from=webpack_build /opt/hunter2/src/webpack-stats.json /opt/hunter2/src/webpack-stats.json
COPY . .

RUN install -d -g hunter2 -o hunter2 /config /uploads/events /uploads/puzzles /uploads/site /uploads/solutions /var/spool/django_prometheus
VOLUME ["/config", "/uploads/events", "/uploads/puzzles", "/uploads/site", "/uploads/solutions"]

USER hunter2

EXPOSE 8000

ENTRYPOINT ["/opt/hunter2/venv/bin/python", "manage.py"]
CMD ["rundaphne", "--bind", "0.0.0.0"]
