FROM node:16.11.0-alpine3.14@sha256:7fa5235f5ccbda27ea38a3f262e47660ae86142c8433f6ba2fb8c87b7269fe36 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
