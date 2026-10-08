FROM node:22-bookworm-slim AS build
ARG ANGULAR_OUTPUT_DIR=dist/atelier-documentaire
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm install --global npm@11.21.0 \
    && npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build \
    && mkdir -p /out \
    && if [ -f "/build/frontend/${ANGULAR_OUTPUT_DIR}/browser/index.html" ]; then \
         cp -a "/build/frontend/${ANGULAR_OUTPUT_DIR}/browser/." /out/; \
       elif [ -f "/build/frontend/${ANGULAR_OUTPUT_DIR}/index.html" ]; then \
         cp -a "/build/frontend/${ANGULAR_OUTPUT_DIR}/." /out/; \
       else \
         echo "Angular browser index.html absent" >&2; exit 1; \
       fi \
    && test -f /out/index.html

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY --from=build /out/ /usr/share/nginx/html/
COPY infrastructure/frontend-nginx.conf /etc/nginx/conf.d/default.conf
USER 101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
