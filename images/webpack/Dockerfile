FROM node:16.14.2-alpine3.15@sha256:32f64135e74ec4dc5d63cc36318444f1d801cd23c44253124f7eccb52c4b89c5 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
