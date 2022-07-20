FROM node:18.6.0-alpine3.15@sha256:a7f8dfe5fc6d984af5a3371f50dd6d485fad8218bc984e39b8277e338a4a3329 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
