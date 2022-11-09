FROM node:18.12.1-alpine3.15@sha256:756b777532b1fed9e1a63ea10a1af1aec919b08e483ba5dda11c5ded1bd586c3 as webpack_build

COPY . /
RUN --mount=type=cache,target=/usr/local/share/.cache/yarn \
    yarn install --frozen-lockfile

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["start"]
