FROM node:18.11.0-alpine3.15@sha256:9b311a13db16af9990d55716a63ba31bac45311a99b41d7cdcd85a5bb84b98ca as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
