FROM node:18.9.0-alpine3.15@sha256:8d1eb5d6dffec25af36b62692179f408a97862eafac53ebccd2fb92f0d3b9d5d as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
