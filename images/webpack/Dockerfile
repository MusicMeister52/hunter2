FROM node:18.4.0-alpine3.15@sha256:f55132b48261c7ca0394d71c204eb419db0a0209be341762390693434e4bdd92 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
