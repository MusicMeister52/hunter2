FROM node:18.12.1-alpine3.15@sha256:0fc9424b8ff43f87bd6b114c461705cd78bd21affc9edc9c707d5e977069ed50 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
