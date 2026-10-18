FROM node:22-alpine AS build
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .

# ⚠️ Doivent correspondre EXACTEMENT aux args du docker-compose
ARG VITE_API_URL
ARG VITE_USE_MOCK
ARG VITE_CLAIMS_API_ENABLED

ENV VITE_API_URL=$VITE_API_URL \
    VITE_USE_MOCK=$VITE_USE_MOCK \
    VITE_CLAIMS_API_ENABLED=$VITE_CLAIMS_API_ENABLED

RUN pnpm build

FROM nginx:alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
