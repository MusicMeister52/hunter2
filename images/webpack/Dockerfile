FROM node:16.14.0-alpine3.15@sha256:2eafdff61134201bb13e452ae5515ac181126d28d91d548b048dab66140adbe6 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
