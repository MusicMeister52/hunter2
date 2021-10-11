FROM node:16.11.0-alpine3.14@sha256:e6b5d56ed96e8035575f0193c1519d22e488ca4de7a9fc856162cb6206510162 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
