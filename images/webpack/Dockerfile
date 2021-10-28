FROM node:16.13.0-alpine3.14@sha256:3bca55259ada636e5fee8f2836aba7fa01fed7afd0652e12773ad44af95868b9 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
