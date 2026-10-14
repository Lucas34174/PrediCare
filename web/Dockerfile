# --- Étape 1 : build de l'application React
FROM node:22-alpine AS build
WORKDIR /app
RUN npm install -g pnpm@10

# Dépendances d'abord
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile  

COPY . .

# Variables lues par Vite AU BUILD
# /api est relayé vers le service api par nginx : pas de CORS à configurer.
ARG VITE_API_URL=/api
ARG VITE_USE_MOCK=true
ENV VITE_API_URL=$VITE_API_URL \
    VITE_USE_MOCK=$VITE_USE_MOCK
RUN pnpm build

# --- Étape 2 : service des fichiers statiques par nginx
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
