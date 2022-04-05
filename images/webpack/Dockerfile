FROM node:16.14.2-alpine3.15@sha256:28bed508446db2ee028d08e76fb47b935defa26a84986ca050d2596ea67fd506 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
