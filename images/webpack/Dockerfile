FROM node:16.14.2-alpine3.15@sha256:5906c27fc9d4a4dbde9d3c78963ccb3f4e1821ffdc99e339ea16d149e7a84155 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
