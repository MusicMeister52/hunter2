# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.2-alpine3.13@sha256:64e7fb64b5d6a39566d0ad25c0692d8454fe5f26e40be0f8b9017476f73890c9

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
