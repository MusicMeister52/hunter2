ARG BUILD_TAG=latest
FROM registry.gitlab.com/hunter2.app/hunter2/app:${BUILD_TAG} AS app

USER root
RUN python manage.py collectstatic

FROM alpine:3.8

RUN apk add --no-cache \
    nginx \
    nginx-mod-http-lua

ADD https://raw.githubusercontent.com/knyar/nginx-lua-prometheus/379c0a4d4d6f3c5b0eb93691fc7e14fff498e1ca/prometheus.lua /usr/lib/lua/5.1/

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=app /static /static

CMD ["nginx", "-g", "daemon off;"]
