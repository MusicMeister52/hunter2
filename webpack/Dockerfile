# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.4.2-alpine3.13@sha256:1cc05b00921e12dc6096af1af1b5dd2e770db3f8181697a189c6dd5dd160ac44

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
