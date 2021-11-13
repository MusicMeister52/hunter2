FROM node:16.13.0-alpine3.14@sha256:3d5f874080844ff102df14186952b09ae51d34602cb86f21d8298643cd5e6b2a as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
