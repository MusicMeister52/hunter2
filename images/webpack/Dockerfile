FROM node:18.12.1-alpine3.15@sha256:cd3a7004267e419477bbfc50e0502df8607a0b9b4465092f6e2c2ce4092faa45 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
