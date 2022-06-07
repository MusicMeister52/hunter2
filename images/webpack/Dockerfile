FROM node:18.3.0-alpine3.15@sha256:7ab82182ec72ea2042e29f40fd2d7badf3023302928600803e2c158be85aee94 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
