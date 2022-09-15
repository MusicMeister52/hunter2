FROM node:18.9.0-alpine3.15@sha256:c943e7d6af86c1b06d82b0ed070fed714652ac8a10e2184ae619eb5249a70947 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
