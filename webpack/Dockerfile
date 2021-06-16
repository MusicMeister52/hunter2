# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.3.0-alpine3.13@sha256:6b56197d33a56cd45d1d1214292b8851fa1b91b2ccc678cee7e5fd4260bd8fae

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
