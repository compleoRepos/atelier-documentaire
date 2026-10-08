from __future__ import annotations

import io
import os
from pathlib import Path
from typing import BinaryIO

from ..core.settings import Settings


class Storage:
    def put(self, key: str, data: bytes | BinaryIO) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def open(self, key: str):
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root != p and self.root not in p.parents:
            raise ValueError("clé de stockage invalide")
        return p

    def put(self, key, data):
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".tmp")
        with open(tmp, "wb") as out:
            if hasattr(data, "read"):
                while chunk := data.read(1024 * 1024):
                    out.write(chunk)
            else:
                out.write(data)
        os.replace(tmp, p)

    def get(self, key):
        with open(self._path(key), "rb") as f:
            return f.read()

    def open(self, key):
        return open(self._path(key), "rb")

    def exists(self, key):
        return self._path(key).is_file()


class S3Storage(Storage):
    def __init__(self, settings: Settings):
        if not settings.s3_bucket or not settings.s3_endpoint_url:
            raise RuntimeError("STORAGE_BACKEND=s3 exige S3_BUCKET et S3_ENDPOINT_URL explicites")
        import boto3
        from botocore.config import Config

        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            config=Config(
                connect_timeout=3, read_timeout=30, retries={"max_attempts": 2, "mode": "standard"}
            ),
        )

    def _key(self, key):
        return f"{self.prefix}/{key}".strip("/")

    def put(self, key, data):
        body = data if hasattr(data, "read") else io.BytesIO(data)
        self.client.upload_fileobj(
            body, self.bucket, self._key(key), ExtraArgs={"ServerSideEncryption": "AES256"}
        )

    def get(self, key):
        return self.client.get_object(Bucket=self.bucket, Key=self._key(key))["Body"].read()

    def open(self, key):
        return io.BytesIO(self.get(key))

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except Exception:
            return False


def make_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(settings.data_dir / "objects")
