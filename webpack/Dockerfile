# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.4.2-alpine3.13@sha256:55cd026b9a7e4b2cbd5d0c67bf0c9feb151798a760a4ede5eb3ef2de026cddec

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
