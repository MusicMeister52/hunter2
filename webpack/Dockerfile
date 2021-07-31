# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.0-alpine3.13@sha256:a55cd676d1aec59d871855b86984063c8854e67a7f552af66418c5068103a509

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
