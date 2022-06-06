ARG H2_IMAGE_VERSION=latest
ARG H2_REGISTRY=registry.gitlab.com/hunter2.app/hunter2
FROM ${H2_REGISTRY}/app:${H2_IMAGE_VERSION} AS app

USER root
RUN /opt/hunter2/venv/bin/python manage.py collectstatic

# Sadly lua-resty-dns-client is not available via OPM so we need luarocks here, which means using the fat image
# https://github.com/Kong/lua-resty-dns-client/issues/136
FROM openresty/openresty:1.21.4.1-alpine-fat@sha256:8cb2572858318dbc8ad26c4d9f2f91b06f929fd4d9a3b8e2d48197d8d755c0e1

RUN --mount=type=cache,target=/var/cache/apk apk add -t build_deps \
    git \
 && opm get knyar/nginx-lua-prometheus=0.20201118 \
 && /usr/local/openresty/luajit/bin/luarocks install lua-resty-dns-client 6.0.2 \
 && apk del build_deps

COPY . /
COPY --from=app /static /static
