FROM node:18.7.0-alpine3.15@sha256:58008ce95c2b116d44a8e69682042402bf53937a794efe4e3a3885f7500c1f23 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
