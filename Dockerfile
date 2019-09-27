# Construct a common base image for creating python wheels and the final image
FROM python:3.7.4-alpine3.10 AS runtime_base

RUN apk add --no-cache \
    lua5.2 \
    postgresql-client \
    postgresql-libs \
    imlib2

# Setup user
RUN addgroup -g 500 -S hunter2 \
 && adduser -h /opt/hunter2 -s /sbin/nologin -G hunter2 -S -u 500 hunter2
WORKDIR /opt/hunter2


# Build image with all the pythong dependancies.
FROM runtime_base AS python_build

RUN apk add --no-cache \
    gcc \
    git \
    libffi-dev \
    linux-headers \
    lua5.2-dev \
    musl-dev \
    postgresql-dev

ARG poetry_version=0.12.17
RUN wget "https://raw.githubusercontent.com/sdispater/poetry/${poetry_version}/get-poetry.py" \
 && python get-poetry.py --version "${poetry_version}" \
 && rm get-poetry.py
ENV PATH "/root/.poetry/bin:${PATH}"

COPY poetry.lock pyproject.toml /opt/hunter2/
RUN poetry config settings.virtualenvs.create false \
 && poetry install --no-interaction -v


# Build all the required Lua components
FROM alpine:3.10 AS lua_build

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
FROM node:12.7.0-alpine as webpack_build

WORKDIR /opt/hunter2
COPY . .

RUN yarn install --frozen-lockfile
RUN ./node_modules/.bin/webpack --config webpack.prod.js


# Build the final image
FROM runtime_base

# Copy in the requried components from the previous build stages
COPY --from=python_build /usr/local/lib/python3.7/site-packages /usr/local/lib/python3.7/site-packages
COPY --from=lua_build /opt/hunter2 /opt/hunter2
COPY --from=webpack_build /opt/hunter2/webpack-stats.json /opt/hunter2/assets /opt/hunter2/
COPY . .

RUN install -d -g hunter2 -o hunter2 /config /uploads/events /uploads/puzzles /uploads/solutions
VOLUME ["/config", "/uploads/events", "/uploads/puzzles", "/uploads/solutions"]

USER hunter2

EXPOSE 8000

ENTRYPOINT ["python", "manage.py"]
CMD ["rundaphne", "--bind", "0.0.0.0"]
