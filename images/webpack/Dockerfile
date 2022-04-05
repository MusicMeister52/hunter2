FROM node:16.14.2-alpine3.15@sha256:99026ffbfde86092cdcc353f2f879f8d331e1c04c04e7e37cf74961ffe4d156d as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
