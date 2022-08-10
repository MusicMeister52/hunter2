FROM node:18.7.0-alpine3.15@sha256:5ac5bba96ad9afb5e992a53301a6ca2a37e9da4e0a1caf57a78c2106f180799e as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
