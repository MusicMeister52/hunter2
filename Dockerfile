FROM registry.gitlab.com/rconan/docker-pipenv:2018.7.1-0 AS req_export

ARG DEVELOPMENT=
COPY Pipfile Pipfile.lock /

RUN pipenv lock -r --keep-outdated > /requirements.txt
RUN [ -z ${DEVELOPMENT} ] || pipenv lock -d -r --keep-outdated >> /requirements.txt


FROM python:3.7.0-alpine3.8 AS python_build

ARG DEVELOPMENT=
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


FROM python:3.7.0-alpine3.8

COPY --from=python_build /usr/local/lib/python3.7/site-packages /usr/local/lib/python3.7/site-packages

WORKDIR /usr/src/app

RUN apk add --no-cache \
    lua5.2 \
    postgresql-client \
    postgresql-libs \
    imlib2
RUN python -m wheel install --force /wheels/*.whl
COPY --from=lua_build /opt/hunter2 /opt/hunter2

COPY . .

RUN addgroup -g 500 -S django \
 && adduser -h /usr/src/app -s /sbin/nologin -G django -S -u 500 django \
 && install -d -g django -o django /config /static /uploads/events /uploads/puzzles /uploads/solutions
USER django

VOLUME ["/config", "/static", "/uploads/events", "/uploads/puzzles", "/uploads/solutions"]

EXPOSE 3031

ENV UWSGI_SOCKET :3031
ENV UWSGI_ENABLE_THREADS True
ENV UWSGI_MASTER True
ENV UWSGI_VACUUM True
ENV UWSGI_UID 500
ENV UWSGI_GID 500
ENV UWSGI_CHDIR /usr/src/app
ENV UWSGI_MODULE hunter2.wsgi:application

ENTRYPOINT ["python", "manage.py"]
CMD ["runuwsgi"]
