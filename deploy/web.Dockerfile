# syntax=docker/dockerfile:1
# Build context is the repository root:  docker build -f deploy/web.Dockerfile .

# A glibc (Debian) image on purpose: it avoids platform-specific optional-dependency problems that
# lock files created on a normal Linux machine can have on Alpine.
FROM node:22-bookworm-slim AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
