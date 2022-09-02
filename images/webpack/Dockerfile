FROM node:18.8.0-alpine3.15@sha256:2e413f23e1542fb4eef3201f3cd0fd9932adb7015f3c24c50ffab6a6dfdcdcb3 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
