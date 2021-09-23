FROM node:16.10.0-alpine3.14@sha256:90414f2e9f0d0e7d87ff350f74f096e7a39a13d8fcaa1b25b940a3acad3a413f as webpack_build

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
