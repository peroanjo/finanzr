FROM node:24-alpine@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf AS dependencies
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci

FROM dependencies AS development
COPY frontend ./
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM dependencies AS build
ARG FINANZR_VERSION=development
ARG FINANZR_COMMIT=desarrollo
ARG FINANZR_DEPLOYED_AT=
ENV VITE_FINANZR_VERSION=${FINANZR_VERSION}
ENV VITE_FINANZR_COMMIT=${FINANZR_COMMIT}
ENV VITE_FINANZR_DEPLOYED_AT=${FINANZR_DEPLOYED_AT}
COPY frontend ./
RUN npm run build

FROM caddy:2.11.7-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f AS production
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/app
RUN cp /usr/bin/caddy /usr/local/bin/caddy-unprivileged
USER 1000:1000
ENTRYPOINT ["caddy-unprivileged"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
EXPOSE 8080
