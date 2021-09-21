# Construct a common base image for creating python wheels and the final image
FROM pypy:3.8-7.3.7-slim-bullseye AS runtime_base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi7 \
    libimlib2 \
    liblua5.3 \
    libpq5 \
 && rm -rf /var/lib/apt/lists/*

# Setup user
RUN adduser --system --home /opt/hunter2 --shell /sbin/nologin --uid 500 --group hunter2
WORKDIR /opt/hunter2/src


# Build image with all the python dependencies.
FROM runtime_base AS python_build

# Suppress pip version warning, we're keeping the version from the docker base image
ARG PIP_DISABLE_PIP_VERSION_CHECK=1

ENV PATH "/root/.poetry/bin:${PATH}"
ARG poetry_version=1.1.4
ADD https://raw.githubusercontent.com/python-poetry/poetry/${poetry_version}/get-poetry.py /usr/local/lib/
# Poetry wants Python to be called `python` or `python3`, let's add both for maximum compatability
RUN ln -s /opt/pypy/bin/pypy3 /usr/local/bin/python3 && ln -s /opt/pypy/bin/pypy3 /usr/local/bin/python
RUN pypy /usr/local/lib/get-poetry.py --version "${poetry_version}"
RUN poetry config virtualenvs.create false
RUN pypy -m venv /opt/hunter2/venv

RUN apt-get update && apt-get install -y --no-install-recommends \
    cargo \
    gcc \
    git \
    libffi-dev \
    liblua5.3-dev \
    libpq-dev \
    libssl-dev \
    pkg-config \
 && rm -rf /var/lib/apt/lists/*

ARG dev_flag=" --no-dev"
COPY poetry.lock pyproject.toml /opt/hunter2/src/
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/root/.cargo \
    . /opt/hunter2/venv/bin/activate \
 && poetry install${dev_flag} --no-root


# Build all the required Lua components
FROM debian:bullseye-slim AS lua_build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libimlib2-dev \
    liblua5.3-dev \
    lua5.3 \
    luarocks \
 && rm -rf /var/lib/apt/lists/*

COPY hunts/runtimes/lua/luarocks/config.lua /etc/luarocks/config-5.3.lua

RUN --mount=type=cache,target=/root/.cache/luarocks \
    luarocks install lua-cjson 2.1.0-1
RUN --mount=type=cache,target=/root/.cache/luarocks \
    luarocks install lua-imlib2 dev-2


# Build the production webpack'ed assets
FROM node:16.13.0-bullseye-slim as webpack_build

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
