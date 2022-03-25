ARG H2_IMAGE_VERSION=latest
ARG H2_REGISTRY=registry.gitlab.com/hunter2.app/hunter2
FROM ${H2_REGISTRY}/app:${H2_IMAGE_VERSION} AS app

USER root
RUN /opt/hunter2/venv/bin/python manage.py collectstatic

# Sadly lua-resty-dns-client is not available via OPM so we need luarocks here, which means using the fat image
# https://github.com/Kong/lua-resty-dns-client/issues/136
FROM openresty/openresty:1.19.9.1-alpine-fat@sha256:5c1bcbff5ac1f5c31dfb207f20702a375a6aba936d48fe8fb3bbdc2d510e2d2e

RUN --mount=type=cache,target=/var/cache/apk apk add -t build_deps \
    git \
 && opm get knyar/nginx-lua-prometheus=0.20201118 \
 && /usr/local/openresty/luajit/bin/luarocks install lua-resty-dns-client 6.0.2 \
 && apk del build_deps

COPY . /
COPY --from=app /static /static
