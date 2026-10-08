FROM golang:1.24.8-bookworm AS build
ARG MINIO_TAG=RELEASE.2025-10-15T17-29-55Z
ARG MINIO_COMMIT=9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a
WORKDIR /src
RUN git clone --depth 1 --branch "${MINIO_TAG}" https://github.com/minio/minio.git minio \
    && test "$(git -C minio rev-parse HEAD)" = "${MINIO_COMMIT}"
WORKDIR /src/minio
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/minio .

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home-dir /data --shell /usr/sbin/nologin minio \
    && mkdir -p /data \
    && chown -R 10001:10001 /data
COPY --from=build /out/minio /usr/local/bin/minio
RUN chmod 0755 /usr/local/bin/minio
USER 10001:10001
WORKDIR /data
VOLUME ["/data"]
EXPOSE 9000 9001
ENTRYPOINT ["/usr/local/bin/minio"]
