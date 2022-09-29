FROM node:18.10.0-alpine3.15@sha256:f3fd2225a51e773623065e8242c616a6a114753fcd40e483f9fed456c991a99a as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
