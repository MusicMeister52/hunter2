FROM node:18.10.0-alpine3.15@sha256:ea4a1955fbf3293fb2642de3e13a50c01c7f23fc40046ed54513bd5939a67def as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
