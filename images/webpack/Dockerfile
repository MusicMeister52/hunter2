FROM node:16.11.0-alpine3.14@sha256:423758cf88673bbeaf6e89425a668892ec9115c4c3a467fd45af15b989338dc4 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
