# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.0-alpine3.13@sha256:5ff93982d7d7dcc416c60ed5a5cd00d833e4c46d34463b67d07416347561b5da

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
