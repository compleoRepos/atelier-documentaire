FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr tesseract-ocr-ara tesseract-ocr-deu tesseract-ocr-eng \
       tesseract-ocr-fra tesseract-ocr-ita tesseract-ocr-nld tesseract-ocr-spa \
       fonts-dejavu fontconfig libreoffice-writer \
    && fc-cache -f \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY infrastructure/docker/production-entrypoint.sh /usr/local/bin/production-entrypoint
RUN mkdir -p /app/runtime /app/models /app/tmp /app/dataset/expected \
    && chmod 755 /usr/local/bin/production-entrypoint \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser
WORKDIR /app/backend

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/production-entrypoint", "python", "-m", "uvicorn"]
CMD ["app.main:app", "--host", "0.0.0.0", "--port", "8000"]
