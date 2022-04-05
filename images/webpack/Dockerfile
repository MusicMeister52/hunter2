FROM node:16.14.2-alpine3.15@sha256:cdf8c05b081837d7afe63e0ae0711152e60a30f3711b5050f9108def2025d513 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
