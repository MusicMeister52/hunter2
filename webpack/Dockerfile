# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.5.0-alpine3.13@sha256:50b33102c307e04f73817dad87cdae145b14782875495ddd950b5a48e4937c70

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
