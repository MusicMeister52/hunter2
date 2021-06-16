# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.3.0-alpine3.13@sha256:8fdfe93e621116e8a7b663dd6d9e1dc0dbc952d6de9b87ad3218d83ba67bfb92

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
