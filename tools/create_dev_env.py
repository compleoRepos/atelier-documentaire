"""Générer une configuration de laboratoire locale ; jamais une configuration bancaire PROD."""

from __future__ import annotations

import argparse
import base64
import os
import secrets
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(".env"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    template = (root / ".env.example").read_text(encoding="utf-8")
    postgres_password = secrets.token_urlsafe(32)
    redis_password = secrets.token_urlsafe(32)
    replacements = {
        "TRANSLATOR_JWT_SECRET": secrets.token_urlsafe(48),
        "POSTGRES_PASSWORD": postgres_password,
        "REDIS_PASSWORD": redis_password,
        "MINIO_ROOT_USER": "minio-" + secrets.token_hex(6),
        "MINIO_ROOT_PASSWORD": secrets.token_urlsafe(32),
        "MINIO_KMS_SECRET_KEY": "dev-only:" + base64.b64encode(secrets.token_bytes(32)).decode(),
        "TRANSLATOR_DATABASE_URL": f"postgresql+psycopg://translator:{postgres_password}@postgres:5432/translator",
        "TRANSLATOR_CELERY_BROKER_URL": f"redis://:{redis_password}@redis:6379/0",
        "TRANSLATOR_ENGINE": "offline",
    }
    lines = []
    for line in template.splitlines():
        key = line.split("=", 1)[0]
        lines.append(f"{key}={replacements[key]}" if key in replacements else line)
    try:
        descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        parser.error(
            "Le fichier existe : refus de modifier les secrets ou de perdre l'accès aux objets chiffrés."
        )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write("\n".join(lines) + "\n")
    print(
        f"Configuration DEV créée : {args.out.resolve()}. Aucun secret affiché. Conserver cette clé tant que des objets chiffrés existent."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
