# syntax=docker/dockerfile:1.1.3-experimental
# Construct a common base image for creating python wheels and the final image
FROM python:3.8.7-alpine3.13@sha256:4b710739b8088ba0e14751845bba81609c05628547bb941968a7928cb7364bf4 AS runtime_base

RUN --mount=type=cache,target=/var/cache/apk apk add \
    lua5.2 \
    postgresql-client \
    postgresql-libs \
    imlib2

# Setup user
RUN addgroup -g 500 -S hunter2 \
 && adduser -h /opt/hunter2 -s /sbin/nologin -G hunter2 -S -u 500 hunter2
WORKDIR /opt/hunter2/src


# Build image with all the pythong dependancies.
FROM runtime_base AS python_build

RUN --mount=type=cache,target=/var/cache/apk apk add \
    gcc \
    git \
    libffi-dev \
    linux-headers \
    lua5.2-dev \
    musl-dev \
    postgresql-dev

# Suppress pip version warning, we're keeping the version from the docker base image
ARG PIP_DISABLE_PIP_VERSION_CHECK=1

ENV PATH "/root/.poetry/bin:${PATH}"
ARG poetry_version=1.1.4
RUN wget "https://raw.githubusercontent.com/python-poetry/poetry/${poetry_version}/get-poetry.py" \
 && python get-poetry.py --version "${poetry_version}" \
 && rm get-poetry.py \
 && poetry config virtualenvs.create false \
 && python -m venv /opt/hunter2/venv

ARG dev_flag=" --no-dev"
COPY poetry.lock pyproject.toml /opt/hunter2/src/
RUN --mount=type=cache,target=/root/.cache/pip \
    . /opt/hunter2/venv/bin/activate \
 && poetry install${dev_flag} --no-root


# Build all the required Lua components
FROM alpine:3.13.2@sha256:a75afd8b57e7f34e4dad8d65e2c7ba2e1975c795ce1ee22fa34f8cf46f96a3be AS lua_build

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
FROM node:14.16.0-alpine3.13@sha256:00eafdb082a1f26bc0a2014abfaac9924533c8838fc8d443780cf9e0c045f64e as webpack_build

WORKDIR /opt/hunter2/src

COPY .yarnrc package.json yarn.lock /opt/hunter2/src/
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

RUN install -d -g hunter2 -o hunter2 /config /uploads/events /uploads/puzzles /uploads/site /uploads/solutions
VOLUME ["/config", "/uploads/events", "/uploads/puzzles", "/uploads/site", "/uploads/solutions"]

USER hunter2

EXPOSE 8000

ENTRYPOINT ["/opt/hunter2/venv/bin/python", "manage.py"]
CMD ["rundaphne", "--bind", "0.0.0.0"]
