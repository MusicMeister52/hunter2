# syntax=docker/dockerfile:1.1.3-experimental
FROM node:16.6.1-alpine3.13@sha256:53ebfa5e6df1e458b47f677cb4f6fd3cf1d079083647dc40d182910a57b5a63d

COPY package.json yarn.lock /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
