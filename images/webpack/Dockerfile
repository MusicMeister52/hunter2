FROM node:18.9.1-alpine3.15@sha256:788711133d4f594dd70ce144482dc2e532336412df44f316bb502ce9d56f665f as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
