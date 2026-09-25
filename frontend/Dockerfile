FROM node:24.13.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2.10.2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/out /srv
EXPOSE 80
