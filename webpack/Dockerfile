# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.0-alpine3.13@sha256:19a246b908cc3ec56ffa865bbf417a11866c71df725fd8495f147776922dcdf6

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
