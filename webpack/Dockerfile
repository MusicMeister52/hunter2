FROM node:16.9.1-alpine3.14@sha256:62f442b1f2be995cb7352df38a77f936cbedf02ca3213f0cf8f61facf74d0d68 as webpack_build

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
