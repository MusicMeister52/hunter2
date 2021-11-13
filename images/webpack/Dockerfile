FROM node:16.13.0-alpine3.14@sha256:0e083ca64d11a629fd105057f57f9ab83f037a935f58a09e7b4788fdef717e7a as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
