FROM node:18.7.0-alpine3.15@sha256:2742806cde6d003a1273392647f040b9bc48db6c3701b620f17f34d7769e69bb as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
