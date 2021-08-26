# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.8.0-alpine3.13@sha256:d93d08839181197fcc0050c540dbd5ae3787568a1a1fec1ba31910c0b433673f

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
