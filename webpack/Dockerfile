# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.3.0-alpine3.13@sha256:f372a9ffcec27159dc9623bad29997a1b61eafbb145dbf4f7a64568be2f59b99

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
