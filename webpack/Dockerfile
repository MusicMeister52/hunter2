FROM node:11.9.0-alpine

COPY package.json yarn.lock /
RUN yarn install --frozen-lockfile

WORKDIR /usr/src/app

EXPOSE 4000
ENTRYPOINT ["yarn"]
CMD ["run", "start"]
