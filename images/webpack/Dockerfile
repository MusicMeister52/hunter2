FROM node:18.10.0-alpine3.15@sha256:96f0b877b028b0b0ab7ba296eb0cee5558fe4920b4cb267c9125324c0c20e312 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
