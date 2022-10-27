FROM node:18.12.0-alpine3.15@sha256:cc01b1f106743660b64c19b5ed6668be7a6523f28229103af5e77c381f68babc as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
