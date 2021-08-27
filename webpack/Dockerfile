# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.8.0-alpine3.13@sha256:abd76715630b2fbed5de9cbcf8b44beb94bfd1ccb972e8dfc3eb5cdf4b1719d0

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
