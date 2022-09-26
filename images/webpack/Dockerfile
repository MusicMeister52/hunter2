FROM node:18.9.1-alpine3.15@sha256:d029138e4c1e9e8eaef955aad2b2502b77496855414b01cb3561c37913e44770 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
