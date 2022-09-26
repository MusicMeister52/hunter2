FROM node:18.9.1-alpine3.15@sha256:20d4ea8ec73808ae2928c705cc3c450a1b86272e51e7d9867b6d26e1eb3f2690 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
