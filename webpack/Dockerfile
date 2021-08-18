# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.2-alpine3.13@sha256:22e6e08e5be7d772daf552e0ac273fd6304bd9c374e5e1596dd4fe5e8c241e1e

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
