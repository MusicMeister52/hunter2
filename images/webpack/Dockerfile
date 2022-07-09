FROM node:18.5.0-alpine3.15@sha256:5ad62659f793e0194c632cfdeeb9a5f052d241a648d2cfba56f8c05497bf5b5f as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
