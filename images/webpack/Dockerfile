FROM node:18.11.0-alpine3.15@sha256:51993636f9b847b869a50fc02b226bea7b1d3c173c4b5bd905e7b4320c4197a6 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
