# syntax=docker/dockerfile:1.7
# Multi-stage frontend Dockerfile.
# Targets: dev (Vite HMR) and prod (nginx serving static build).

ARG NODE_VERSION=20-alpine

# =============================================================================
# Base — pnpm via corepack
# =============================================================================
FROM node:${NODE_VERSION} AS base
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
WORKDIR /app

# =============================================================================
# Deps — install once, cache layer
# =============================================================================
FROM base AS deps
COPY package.json pnpm-lock.yaml* ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile || pnpm install

# =============================================================================
# Dev — hot module reload (source mounted at runtime)
# =============================================================================
FROM deps AS dev
COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

# =============================================================================
# Build — produce static dist/
# =============================================================================
FROM deps AS build
COPY . .
RUN pnpm build

# =============================================================================
# Prod — nginx serving static
# =============================================================================
FROM nginx:1.27-alpine AS prod
RUN apk add --no-cache curl
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Run as non-root
RUN chown -R nginx:nginx /usr/share/nginx/html
USER nginx

EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD curl -fsS http://localhost:8080/ || exit 1
