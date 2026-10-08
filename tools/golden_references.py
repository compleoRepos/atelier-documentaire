"""Références humaines locales : portée tenant explicite et origine liée au SHA256."""

from __future__ import annotations

import json
import re
from pathlib import Path


def load_reference(expected_dir: Path, sha256: str, tenant_id: str | None = None) -> dict | None:
    if not re.fullmatch(r"[a-fA-F0-9]{64}", sha256):
        return None
    if tenant_id and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tenant_id):
        raise ValueError("Identifiant de tenant invalide")
    scope = expected_dir / tenant_id if tenant_id else expected_dir
    candidates = list((scope / sha256).glob("v*.json"))
    if (scope / f"{sha256}.json").is_file():
        candidates.append(scope / f"{sha256}.json")
    references = []
    for path in candidates:
        try:
            reference = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(reference, dict):
            continue
        if reference.get("approved") is not True or reference.get("source_sha256") != sha256:
            continue
        if tenant_id and reference.get("tenant_id", tenant_id) != tenant_id:
            continue
        if not reference.get("reviewer_id") or not reference.get("validated_at"):
            continue
        version = reference.get("version")
        if isinstance(version, bool) or not isinstance(version, int) or version < 1:
            continue
        references.append(reference)
    return max(references, key=lambda item: item["version"]) if references else None
