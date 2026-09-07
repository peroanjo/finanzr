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

FROM caddy:2.11.4-alpine@sha256:5f5c8640aae01df9654968d946d8f1a56c497f1dd5c5cda4cf95ab7c14d58648 AS production
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/app
RUN cp /usr/bin/caddy /usr/local/bin/caddy-unprivileged
USER 1000:1000
ENTRYPOINT ["caddy-unprivileged"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
EXPOSE 8080
