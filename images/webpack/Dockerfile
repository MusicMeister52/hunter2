FROM node:18.11.0-alpine3.15@sha256:5ce340fcbba9690d6ba304a8b9025877f6520c86e2a709a5fe82f36a7bd5cd4f as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
