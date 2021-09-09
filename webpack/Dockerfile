FROM node:16.9.0-alpine3.14@sha256:82558d49922838cec5fe3220ab00245d64c6980099b1d1bbf83a8ecbffebbe8d as webpack_build

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
