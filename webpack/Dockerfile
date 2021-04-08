# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.1-alpine3.13@sha256:4ffbef007b0214706fb8ec92353ccd5b0a12d9d1522e0f2c5e0a8bde3f9d8985

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
