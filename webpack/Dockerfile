# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.2-alpine3.13@sha256:bd39f3e62841ba73ed86eec0edfd1b1867ae2153b491545726ece4e328ba54fc

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
