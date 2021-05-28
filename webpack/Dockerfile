# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.2.0-alpine3.13@sha256:e5615005591e2450e782fa82b10bf31e4c3a90b00f4f47f3691bcb4c03c5b1a2

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
