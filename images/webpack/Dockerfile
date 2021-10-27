FROM node:16.13.0-alpine3.14@sha256:5b041be5413e98aca3c6588fcc0b655df82fe6049695a5265aab1582c467af02 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
