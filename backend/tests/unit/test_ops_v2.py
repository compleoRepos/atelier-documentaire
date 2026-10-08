from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


def _load(name: str):
    path = Path(__file__).parents[3] / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_release_gate_rejects_bool_only_approval(tmp_path):
    gate = _load("release_gate")
    result = gate.evaluate_attestation(
        {"approved": True},
        environment="production",
        repository_root=tmp_path,
        proof_path=tmp_path / "proof.json",
    )
    assert result["status"] == "blocked"
    assert any("schema" in item for item in result["errors"])


def test_backup_dry_run_is_planned_and_does_not_write(tmp_path):
    backup = _load("ops_backup")
    destination = tmp_path / "planned"
    result = backup.backup(
        destination=destination,
        postgres_dsn="postgresql://example.invalid/db",
        s3_bucket="private",
        dry_run=True,
    )
    assert result["state"] == "planned"
    assert not destination.exists()


def test_restore_validates_hashes_and_dry_run_never_reports_success(tmp_path):
    restore = _load("ops_restore")
    backup_dir = tmp_path / "backup"
    backup_dir.mkdir()
    dump = backup_dir / "database.dump"
    dump.write_bytes(b"synthetic database dump")
    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    (backup_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "atelier-backup/v1",
                "database": {"dump": "database.dump", "sha256": digest},
                "s3": {"bucket": "source", "prefix": "source/", "objects": []},
            }
        )
    )
    result = restore.restore(
        backup_dir=backup_dir,
        destination=tmp_path / "restore",
        target_postgres_dsn="postgresql://example.invalid/quarantine",
        target_s3_bucket="target",
        target_s3_prefix="restore/1",
        dry_run=True,
    )
    assert result["state"] == "planned"
    assert result["state"] != "success"
