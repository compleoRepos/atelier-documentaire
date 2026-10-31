# syntax=docker/dockerfile:1
# Service OCR local Surya (moteur OCR par défaut du produit).
# - Aucun poids inclus : licence des poids Surya à attester par l'exploitant (docs/ocr/SURYA.md) ;
#   les fichiers GGUF sont montés en lecture seule sur /models et contrôlés par SHA-256 au démarrage.
# - llama.cpp = archive officielle b11700 (CPU x64), empreinte publiée vérifiée à la construction ;
#   binaire identique (octet pour octet) à celui mesuré pendant la qualification LOT 2.2.
# - Exécution sans accès réseau sortant (réseau interne) : HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE.
FROM python:3.12-slim-bookworm

ARG LLAMA_CPP_BUILD=b11700
ARG LLAMA_CPP_SHA256=51842656431fc20928123e0c88598f7604a2fe2031fb4e7d45943316817de024

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl libgomp1 libssl3 \
 && curl -fsSL -o /tmp/llama.tgz \
      "https://github.com/ggml-org/llama.cpp/releases/download/${LLAMA_CPP_BUILD}/llama-${LLAMA_CPP_BUILD}-bin-ubuntu-x64.tar.gz" \
 && echo "${LLAMA_CPP_SHA256}  /tmp/llama.tgz" | sha256sum -c - \
 && mkdir -p /opt/llama \
 && tar -xzf /tmp/llama.tgz -C /opt/llama --strip-components=1 \
 && rm -f /tmp/llama.tgz \
 && /opt/llama/llama-server --version \
 && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY services/ocr-surya/requirements.lock /tmp/requirements.lock
RUN python -m venv /opt/surya \
 && /opt/surya/bin/pip install --no-cache-dir --no-deps \
      --extra-index-url https://download.pytorch.org/whl/cpu -r /tmp/requirements.lock \
 && /opt/surya/bin/pip check \
 && rm -f /tmp/requirements.lock

COPY services/ocr-surya/ocr_surya_service.py services/ocr-surya/selftest.py services/ocr-surya/entrypoint.sh /opt/ocr-surya/
RUN useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin ocr \
 && chmod 0555 /opt/ocr-surya/entrypoint.sh /opt/ocr-surya/ocr_surya_service.py /opt/ocr-surya/selftest.py

ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    HOME=/tmp XDG_CACHE_HOME=/tmp/cache TORCH_HOME=/tmp/torch HF_HOME=/tmp/hf \
    OCR_SURYA_MODELS=/models OCR_SURYA_BIND=0.0.0.0 OCR_SURYA_PORT=8093 OCR_SURYA_ALLOW_NON_LOOPBACK=1
USER 10001
EXPOSE 8093
HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
  CMD ["/opt/surya/bin/python", "-c", "import urllib.request,sys; sys.exit(0 if b'ok' in urllib.request.urlopen('http://127.0.0.1:8093/health', timeout=3).read() else 1)"]
ENTRYPOINT ["/opt/ocr-surya/entrypoint.sh"]
