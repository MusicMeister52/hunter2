# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.2-alpine3.13@sha256:4e70ed424e6310602d6137b353cc3e0ae066c4214ce17967ca9336b80b3a7fbd

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
