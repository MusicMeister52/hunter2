# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.7.0-alpine3.13@sha256:597864180891b2498e104ace823507882aa9ae132115af63dd8fc611bb300984

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
