FROM node:18.11.0-alpine3.15@sha256:24f8943e2108720e348e29597aeaafed3e16f280953ba010546bf47c848d9b7a as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
