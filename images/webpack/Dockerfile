FROM node:16.14.2-alpine3.15@sha256:72a490e7ed8aed68e16b8dc8f37b5bcc35c5b5c56ee3256effcdee63e2546f93 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
