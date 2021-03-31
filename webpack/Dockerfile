# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.0-alpine3.13@sha256:f9b946bba4247b8d3dffea5a92c0ad351a7c2c6bda03179aa41fb8e314bfec42

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
