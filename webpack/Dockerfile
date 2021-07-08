# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.4.2-alpine3.13@sha256:b7e2d75ecd585feed57be69cd3dee973e5c498241e64906899b3baa2169fb35a

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
