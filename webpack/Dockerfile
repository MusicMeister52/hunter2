# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.2-alpine3.13@sha256:f80bf0b8ce2905366ea1734545a04d76fb76c1768645753e6bb0d22ee789d371

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
