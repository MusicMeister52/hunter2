FROM node:18.10.0-alpine3.15@sha256:54b455407f76ab02370c0b33cc921f813fb3c59295c1e4fdf8456b7ee25eba5f as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
