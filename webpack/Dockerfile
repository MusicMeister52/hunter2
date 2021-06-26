# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.3.0-alpine3.13@sha256:3e0f83e34a8a3e03d96e78fac8412b83790896c0abd4b112c7f6d0dcef60bca6

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
