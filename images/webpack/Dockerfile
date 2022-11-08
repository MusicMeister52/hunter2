FROM node:18.12.1-alpine3.15@sha256:57a66de5748f44e7a9ce08f78eb3a29b5c084fb513a85f51b8953c2c8d8654fa as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
