#!/usr/bin/env python3
"""Validate and restore an Atelier backup into explicitly isolated targets.

A restore requires ``--confirm`` and refuses to use the source database/bucket
identity from the manifest.  It never drops objects or schemas and never uses
``--clean``/``--create`` with pg_restore.  Dry runs return ``planned``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_validate_manifest(backup_dir: Path) -> dict[str, Any]:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "atelier-backup/v1":
        raise ValueError("unsupported backup manifest schema")
    database = manifest.get("database", {})
    dump = backup_dir / str(database.get("dump", ""))
    if not dump.is_file() or sha256_file(dump) != database.get("sha256"):
        raise ValueError("database dump hash validation failed")
    for item in manifest.get("s3", {}).get("objects", []):
        path = backup_dir / str(item.get("relative_path", ""))
        if (
            not path.is_file()
            or path.stat().st_size != item.get("size")
            or sha256_file(path) != item.get("sha256")
        ):
            raise ValueError(f"S3 object hash validation failed: {item.get('key')}")
    return manifest


def _db_name(dsn: str) -> str:
    parsed = urlparse(dsn)
    return parsed.path.lstrip("/").split("?", 1)[0]


def _boto3_client(endpoint_url: str | None, region: str):
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError("boto3 is required for S3 restore (use the project venv)") from exc
    return boto3.client("s3", endpoint_url=endpoint_url or None, region_name=region)


def _restore_db(dump: Path, dsn: str) -> None:
    if shutil.which("pg_restore") is None:
        raise RuntimeError("pg_restore is required for PostgreSQL restore")
    completed = subprocess.run(
        [
            "pg_restore",
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            dsn,
            str(dump),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(
            f"pg_restore failed ({completed.returncode}): {completed.stderr[-1000:]}"
        )


def restore(
    *,
    backup_dir: Path,
    destination: Path,
    target_postgres_dsn: str,
    target_s3_bucket: str,
    target_s3_prefix: str,
    target_s3_endpoint_url: str | None = None,
    region: str = "us-east-1",
    confirm: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    manifest = load_and_validate_manifest(backup_dir)
    source_db = str(manifest.get("database", {}).get("database_name", ""))
    target_db = _db_name(target_postgres_dsn)
    source_bucket = manifest.get("s3", {}).get("bucket")
    source_prefix = manifest.get("s3", {}).get("prefix", "")
    if not target_postgres_dsn or not target_s3_bucket or not target_s3_prefix:
        raise ValueError("isolated target DSN, bucket and non-empty prefix are required")
    if source_db and source_db == target_db:
        raise ValueError(
            "target PostgreSQL database matches source identity; use an isolated database"
        )
    if source_bucket == target_s3_bucket and str(source_prefix).rstrip(
        "/"
    ) == target_s3_prefix.rstrip("/"):
        raise ValueError("target S3 bucket/prefix matches source identity")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("restore destination must be absent or empty")
    result: dict[str, Any] = {
        "schema": "atelier-restore/v1",
        "state": "planned" if dry_run else "blocked",
        "created_at": datetime.now(UTC).isoformat(),
        "backup_manifest": str(backup_dir / "manifest.json"),
        "target": {"database": target_db, "bucket": target_s3_bucket, "prefix": target_s3_prefix},
        "validated_objects": len(manifest.get("s3", {}).get("objects", [])),
    }
    if dry_run:
        return result
    if not confirm:
        raise ValueError("actual restore requires --confirm; dry-run is the safe default")
    destination.mkdir(parents=True, exist_ok=True)
    _restore_db(backup_dir / str(manifest["database"]["dump"]), target_postgres_dsn)
    client = _boto3_client(target_s3_endpoint_url, region)
    source_key_prefix = str(source_prefix).rstrip("/")
    source_key_prefix = f"{source_key_prefix}/" if source_key_prefix else ""
    uploaded = 0
    for item in manifest.get("s3", {}).get("objects", []):
        source = backup_dir / str(item["relative_path"])
        source_key = str(item["key"])
        relative_key = (
            source_key[len(source_key_prefix) :]
            if source_key_prefix and source_key.startswith(source_key_prefix)
            else source_key
        )
        relative_key = relative_key.lstrip("/")
        if not relative_key or ".." in Path(relative_key).parts:
            raise ValueError(f"unsafe target S3 key derived from: {source_key}")
        key = f"{target_s3_prefix.rstrip('/')}/{relative_key}"
        with source.open("rb") as stream:
            client.upload_fileobj(stream, target_s3_bucket, key)
        uploaded += 1
    result.update({"state": "success", "uploaded_objects": uploaded})
    (destination / "restore-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--target-postgres-dsn", default=os.getenv("OPS_RESTORE_DATABASE_URL", ""))
    parser.add_argument("--target-s3-bucket", default=os.getenv("OPS_RESTORE_S3_BUCKET", ""))
    parser.add_argument("--target-s3-prefix", default=os.getenv("OPS_RESTORE_S3_PREFIX", ""))
    parser.add_argument(
        "--target-s3-endpoint-url", default=os.getenv("OPS_RESTORE_S3_ENDPOINT_URL")
    )
    parser.add_argument("--region", default=os.getenv("TRANSLATOR_S3_REGION", "us-east-1"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        result = restore(
            backup_dir=args.backup_dir,
            destination=args.destination,
            target_postgres_dsn=args.target_postgres_dsn,
            target_s3_bucket=args.target_s3_bucket,
            target_s3_prefix=args.target_s3_prefix,
            target_s3_endpoint_url=args.target_s3_endpoint_url,
            region=args.region,
            confirm=args.confirm,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(json.dumps({"schema": "atelier-restore/v1", "state": "failed", "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] == "planned" or result["state"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
