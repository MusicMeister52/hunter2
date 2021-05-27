# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.2.0-alpine3.13@sha256:0ab1ce23a4a5975b47f98204328604ff761d6f9aaf8f7b4506b31a042333e6d7

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
