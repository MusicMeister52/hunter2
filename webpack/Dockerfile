# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.3.0-alpine3.13@sha256:2eee2f439d3b3509bbe40faff6584bd31b5745b4c137e93e2d795899a2927762

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
