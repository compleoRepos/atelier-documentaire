FROM golang:1.24.8-bookworm AS build
ARG MC_TAG=RELEASE.2025-08-13T08-35-41Z
ARG MC_COMMIT=7394ce0dd2a80935aded936b09fa12cbb3cb8096
WORKDIR /src
RUN git clone --depth 1 --branch "${MC_TAG}" https://github.com/minio/mc.git mc \
    && test "$(git -C mc rev-parse HEAD)" = "${MC_COMMIT}"
WORKDIR /src/mc
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o /out/mc .

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home-dir /tmp --shell /usr/sbin/nologin mc
COPY --from=build /out/mc /usr/local/bin/mc
RUN chmod 0755 /usr/local/bin/mc
USER 10001:10001
ENTRYPOINT ["/usr/local/bin/mc"]
