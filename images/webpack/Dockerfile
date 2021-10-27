FROM node:16.13.0-alpine3.14@sha256:884bacc37c336bfd4a341560ccc55e7b4b107a6e38846931fac461eaf43808d2 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
