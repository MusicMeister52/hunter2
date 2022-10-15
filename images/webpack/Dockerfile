FROM node:18.11.0-alpine3.15@sha256:5d74ba7227beb6719770fd5f2ff6ee61c2cb9efd9200e43a9781e0ba40c8271b as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
