ARG BUILD_TAG=latest
ARG IMAGE_TAG=registry.gitlab.com/hunter2.app/hunter2/app:${BUILD_TAG}
FROM ${IMAGE_TAG} AS app

USER root
RUN /opt/hunter2/venv/bin/python manage.py collectstatic

# Sadly lua-resty-dns-client is not available via OPM so we need luarocks here, which means using the fat image
# https://github.com/Kong/lua-resty-dns-client/issues/136
FROM openresty/openresty:1.19.9.1-alpine-fat@sha256:44afd318a3d189ced0959ba812ed908733d684052113b598b6478c5c09981956

RUN --mount=type=cache,target=/var/cache/apk apk add -t build_deps \
    git \
 && opm get knyar/nginx-lua-prometheus=0.20201118 \
 && /usr/local/openresty/luajit/bin/luarocks install lua-resty-dns-client 6.0.2 \
 && apk del build_deps

COPY . /
COPY --from=app /static /static
