FROM node:16.9.1-alpine3.14@sha256:ed9d6d92d19dcdeb2987275e6309f92fb72889bee97559328f1de041430b17b8 as webpack_build

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
