#!/usr/bin/env python3
"""Safe, streaming backup of PostgreSQL and an S3-compatible bucket.

The command never writes a backup over an existing destination.  ``--dry-run``
only validates prerequisites and reports ``planned``; it is never reported as
successful.  Secrets are read from arguments/environment but never persisted
in the manifest or result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
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


def _require_new_destination(destination: Path, dry_run: bool) -> None:
    if destination.exists():
        if not dry_run:
            raise ValueError(f"destination must not already exist: {destination}")
        if not destination.is_dir():
            raise ValueError("dry-run destination must be a directory path")
    elif not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)


def _boto3_client(endpoint_url: str | None, region: str):
    try:
        import boto3  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised in minimal hosts
        raise RuntimeError("boto3 is required for S3 backup (use the project venv)") from exc
    return boto3.client("s3", endpoint_url=endpoint_url or None, region_name=region)


def _backup_s3(client: Any, bucket: str, prefix: str, root: Path) -> list[dict[str, Any]]:
    objects_root = root / "s3"
    objects_root.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item["Key"])
            relative = key[len(prefix) :].lstrip("/") if prefix else key
            if not relative or relative.startswith("/") or ".." in Path(relative).parts:
                raise ValueError(f"unsafe S3 key relative path: {key}")
            target = objects_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("wb") as stream:
                client.download_fileobj(bucket, key, stream)
            entries.append(
                {
                    "key": key,
                    "relative_path": str(Path("s3") / relative),
                    "size": target.stat().st_size,
                    "sha256": sha256_file(target),
                    "etag": str(item.get("ETag", "")).strip('"'),
                }
            )
    return entries


def _run_pg_dump(dsn: str, target: Path) -> None:
    if shutil.which("pg_dump") is None:
        raise RuntimeError("pg_dump is required for a PostgreSQL backup")
    completed = subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(target), dsn],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode:
        raise RuntimeError(f"pg_dump failed ({completed.returncode}): {completed.stderr[-1000:]}")


def _database_name(dsn: str) -> str:
    """Return only the database path component; never persist credentials."""
    parsed = urlparse(dsn)
    return parsed.path.lstrip("/").split("?", 1)[0]


def backup(
    *,
    destination: Path,
    postgres_dsn: str,
    s3_bucket: str,
    s3_prefix: str = "",
    s3_endpoint_url: str | None = None,
    region: str = "us-east-1",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create a backup and return its public, secret-free result object."""
    _require_new_destination(destination, dry_run)
    if not postgres_dsn or not s3_bucket:
        raise ValueError("postgres_dsn and s3_bucket are required")
    result: dict[str, Any] = {
        "schema": "atelier-backup/v1",
        "state": "planned" if dry_run else "running",
        "destination": str(destination),
        "created_at": datetime.now(UTC).isoformat(),
        "database": {"dump": "database.dump", "format": "custom"},
        "s3": {"bucket": s3_bucket, "prefix": s3_prefix, "objects": []},
    }
    if dry_run:
        result["checks"] = {"pg_dump": bool(shutil.which("pg_dump")), "s3_client": "boto3"}
        return result

    destination.mkdir(parents=False)
    temporary = Path(tempfile.mkdtemp(prefix="atelier-backup-", dir=destination.parent))
    try:
        dump_path = temporary / "database.dump"
        _run_pg_dump(postgres_dsn, dump_path)
        client = _boto3_client(s3_endpoint_url, region)
        objects = _backup_s3(client, s3_bucket, s3_prefix, temporary)
        manifest = {
            "schema": "atelier-backup/v1",
            "created_at": result["created_at"],
            "database": {
                "dump": "database.dump",
                "format": "custom",
                "database_name": _database_name(postgres_dsn),
                "sha256": sha256_file(dump_path),
                "size": dump_path.stat().st_size,
            },
            "s3": {"bucket": s3_bucket, "prefix": s3_prefix, "objects": objects},
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )
        temporary.rename(destination)
        result.update({"state": "success", "manifest": str(destination / "manifest.json")})
        result["database"] = manifest["database"]
        result["s3"] = manifest["s3"]
        return result
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        try:
            destination.rmdir()
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument(
        "--postgres-dsn", default=os.getenv("TRANSLATOR_DATABASE_URL"), required=False
    )
    parser.add_argument("--s3-bucket", default=os.getenv("TRANSLATOR_S3_BUCKET"), required=False)
    parser.add_argument("--s3-prefix", default=os.getenv("OPS_S3_PREFIX", ""))
    parser.add_argument("--s3-endpoint-url", default=os.getenv("TRANSLATOR_S3_ENDPOINT_URL"))
    parser.add_argument("--region", default=os.getenv("TRANSLATOR_S3_REGION", "us-east-1"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        result = backup(
            destination=args.destination,
            postgres_dsn=args.postgres_dsn or "",
            s3_bucket=args.s3_bucket or "",
            s3_prefix=args.s3_prefix,
            s3_endpoint_url=args.s3_endpoint_url,
            region=args.region,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(json.dumps({"schema": "atelier-backup/v1", "state": "failed", "error": str(exc)}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["state"] in {"success", "planned"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
