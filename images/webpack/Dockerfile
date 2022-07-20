FROM node:18.6.0-alpine3.15@sha256:2dcd171c048773051163b4453bfa0df183347f5c5c2074f6bcd7f8df704fba3c as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
