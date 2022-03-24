FROM node:16.14.2-alpine3.15@sha256:da7ef512955c906b6fa84a02295a56d0172b2eb57e09286ec7abc02cfbb4c726 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
