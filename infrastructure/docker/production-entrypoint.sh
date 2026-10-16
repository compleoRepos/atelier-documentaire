#!/bin/sh
set -eu

if [ "${TRANSLATOR_ENVIRONMENT:-local}" = "production" ]; then
  [ "${TRANSLATOR_ENGINE:-}" = "private" ] || { echo 'production requires TRANSLATOR_ENGINE=private' >&2; exit 78; }
  case "${TRANSLATOR_PRIVATE_AI_BASE_URL:-}" in
    https://*) : ;;
    *) echo 'production requires an HTTPS private AI endpoint' >&2; exit 78 ;;
  esac
  hosts="${TRANSLATOR_PRIVATE_AI_ALLOWED_HOSTS:-}"
  [ -n "$hosts" ] || { echo 'production requires a private AI host allowlist' >&2; exit 78; }
  case "$hosts" in
    *'*'*|*'localhost'*|*'127.0.0.1'*|*'0.0.0.0'*) echo 'public/loopback AI host allowlist is forbidden in production' >&2; exit 78 ;;
  esac
  [ "${TRANSLATOR_STORAGE_BACKEND:-}" = "s3" ] || { echo 'production requires private S3 storage' >&2; exit 78; }
  [ "${TRANSLATOR_AV_SCAN_ENABLED:-false}" = "true" ] && [ "${TRANSLATOR_AV_SCAN_REQUIRED:-false}" = "true" ] || {
    echo 'production requires mandatory antivirus scanning (TRANSLATOR_AV_SCAN_*)' >&2; exit 78;
  }
  case "${TRANSLATOR_ALLOWED_ORIGINS:-}" in
    *'*'*|http://*) echo 'production CORS origins must be explicit HTTPS origins' >&2; exit 78 ;;
  esac
  [ "${HF_HUB_OFFLINE:-1}" = "1" ] && [ "${TRANSFORMERS_OFFLINE:-1}" = "1" ] || {
    echo 'production must not download model weights at runtime' >&2; exit 78;
  }
fi
exec "$@"
