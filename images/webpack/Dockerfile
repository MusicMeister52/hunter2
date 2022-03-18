FROM node:16.14.2-alpine3.15@sha256:45234da200a9ded1bc625b414d5d33bc5ca320cfa00d93ff572decae17df3a7c as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
