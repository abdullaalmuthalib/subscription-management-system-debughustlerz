# syntax=docker/dockerfile:1
FROM node:22-slim AS base
WORKDIR /app
RUN apt-get update -y && apt-get install -y --no-install-recommends openssl ca-certificates && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS build
COPY . .
RUN npx prisma generate && npm run build

# Used by the one-shot migrate service
FROM deps AS tools
COPY prisma ./prisma

# Runs the worker with the full dependency tree (tsx)
FROM build AS worker
ENV NODE_ENV=production
USER node
CMD ["npx", "tsx", "src/worker/index.ts"]

FROM base AS web
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER node
EXPOSE 3000
CMD ["node", "server.js"]
