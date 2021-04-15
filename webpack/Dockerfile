# syntax=docker/dockerfile:1.1.3-experimental
FROM node:14.16.1-alpine3.13@sha256:7021600941a9caa072c592b6a89cec80e46cb341d934f1868220f5786f236f60

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
