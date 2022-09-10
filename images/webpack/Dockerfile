FROM node:18.9.0-alpine3.15@sha256:1237b48f79f36ebe9a577ce50bf115a34970fdb61fe8ac2d34ee372289a78051 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
