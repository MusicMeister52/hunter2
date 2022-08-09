FROM node:18.7.0-alpine3.15@sha256:2ec92187fa3c46d888d3eb5ec494ab363fe6392847e25a3af2765b84e4155c33 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
