FROM node:16.8.0-alpine3.14@sha256:e9dec0675a05bded5e881c6839461c2209a4abd8bd16239daf2e59db57c4adaf as webpack_build

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
