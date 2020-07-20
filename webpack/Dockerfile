# syntax=docker/dockerfile:1.1.3-experimental
FROM node:12.18.2-alpine3.12

WORKDIR /
COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn --modules-folder /node_modules install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn", "--modules-folder", "/node_modules"]
CMD ["start"]
