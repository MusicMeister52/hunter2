FROM node:18.6.0-alpine3.15@sha256:f4607fb719c54b28bbe817753a38b2b0b709bdee0e5273bd83a5b537c5baef45 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
