FROM node:18.7.0-alpine3.15@sha256:8d164058ef752b8885a3037cc09dac7c3262b850d67eadeb423c127b6efba464 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
