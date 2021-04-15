# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.1-alpine3.13@sha256:acd9e5d46f97ab8b1741f40a47b63d456237229c153032c0d992d6d5839c93d9

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
