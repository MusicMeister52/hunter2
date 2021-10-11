FROM node:16.11.0-alpine3.14@sha256:dc5397a0900e7eb4cedbf571e17f05d3b7a86440c47c6a5ccc0b2e570957080a as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
