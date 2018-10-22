ARG app_tag=latest
FROM registry.gitlab.com/hunter2.app/hunter2/app:${app_tag} AS app

USER root
RUN python manage.py collectstatic

FROM nginx:1.14.0-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=app /static /static
