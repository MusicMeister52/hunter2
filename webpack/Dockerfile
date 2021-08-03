# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.1-alpine3.13@sha256:976d0b9fbb88e2796019615b8a29de54c6559fb887f115dd22e6a2804e0b3063

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
