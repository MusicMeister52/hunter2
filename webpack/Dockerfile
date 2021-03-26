# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.0-alpine3.13@sha256:00eafdb082a1f26bc0a2014abfaac9924533c8838fc8d443780cf9e0c045f64e

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
