FROM node:18.12.1-alpine3.15@sha256:6cfc7f9ba585c606fbfc696d3633e71242289e0fed37e35038f444dc1d089719 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
