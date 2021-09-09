FROM node:16.9.0-alpine3.14@sha256:325fad54e700a5757709ed3a2c2a3c3e054eb8f7ec7a81202f4286459e924684 as webpack_build

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
