ARG BUILD_TAG=latest
ARG IMAGE_TAG=registry.gitlab.com/hunter2.app/hunter2/app:${BUILD_TAG}
FROM ${IMAGE_TAG} AS app

USER root
RUN /opt/hunter2/venv/bin/python manage.py collectstatic

# Sadly lua-resty-dns-client is not available via OPM so we need luarocks here, which means using the fat image
# https://github.com/Kong/lua-resty-dns-client/issues/136
FROM openresty/openresty:1.19.9.1-alpine-fat@sha256:65d0772e89f2e3f8bb3980949d342e38f6cb4ee1520efa6fefd7d241fe6ff194

RUN --mount=type=cache,target=/var/cache/apk apk add -t build_deps \
    git \
 && opm get knyar/nginx-lua-prometheus=0.20201118 \
 && /usr/local/openresty/luajit/bin/luarocks install lua-resty-dns-client 6.0.2 \
 && apk del build_deps

COPY . /
COPY --from=app /static /static
