# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.0-alpine3.13@sha256:eb2b2be77fbb7515ba116dbf20b55df0523e9d32e0c7b22bb5d625bdd0ad9109

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
