FROM node:16.13.1-alpine3.14@sha256:9643633d0a6817f794b77d1d46c86cb461b5af937ca68d336fd73a4e3d198c91 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
