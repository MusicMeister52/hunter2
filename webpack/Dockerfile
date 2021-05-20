# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.2.0-alpine3.13@sha256:65f488a99e7eb9899dd4ed35cadbea85f64eb3d51604962375bc118a2082f4e5

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
