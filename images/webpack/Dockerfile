FROM node:16.14.2-alpine3.15@sha256:0fd2bf310ee0724673f6665da03300086f88488b62990f82f31baed93a92cd99 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
