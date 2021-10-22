FROM node:16.12.0-alpine3.14@sha256:1c00ed4786872d43c5d4519bffc9e9141b07effdd0573d204fd744af05fce1d5 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
