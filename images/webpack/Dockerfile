FROM node:16.14.2-alpine3.15@sha256:e1c1cdbde9e6ec33399c874fbf40135d0ed493daf7e819e2365909cbd290aee0 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
