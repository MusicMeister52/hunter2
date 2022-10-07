FROM node:18.10.0-alpine3.15@sha256:e2e77eeb87e4f6f5388f786a878dd1589a03298f84e8805bc75251d9db01af3e as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
