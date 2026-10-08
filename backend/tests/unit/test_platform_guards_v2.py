from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.db import init_db
from app.core.settings import Settings
from app.infrastructure.antivirus import scan_upload

ROOT = Path(__file__).resolve().parents[2]


def test_alembic_upgrade_downgrade_and_readiness_guard(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'migrated.db'}")
    config = Config(str(ROOT / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    assert "revoked_sessions" in inspect(engine).get_table_names()
    assert "analysis_snapshot" in {
        column["name"] for column in inspect(engine).get_columns("document_versions")
    }
    settings = Settings(auto_create_schema=False)
    init_db(engine, settings)
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "0001_baseline")
    assert "revoked_sessions" not in inspect(engine).get_table_names()
    with pytest.raises(RuntimeError, match="MIGRATION_REQUIRED"):
        init_db(engine, settings)
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    init_db(engine, settings)
    engine.dispose()


def test_production_cannot_start_with_offline_dev_defaults():
    with pytest.raises(ValueError, match="Production"):
        Settings(environment="production")


@pytest.mark.parametrize(
    "values",
    [
        {"max_context": 32769},
        {"target_input": 25000},
        {"quality_thresholds": {"ocr_score": True}},
        {"quality_thresholds": {"ocr_score": float("nan")}},
        {"job_hard_timeout_seconds": 100, "job_soft_timeout_seconds": 100},
    ],
)
def test_invalid_quality_budget_or_timeout_is_rejected(values):
    with pytest.raises(ValueError):
        Settings(**values)


def test_antivirus_unavailable_is_not_a_clean_result(monkeypatch):
    import socket

    from fastapi import HTTPException

    def unavailable(*args, **kwargs):
        raise OSError("synthetic AV unavailable")

    monkeypatch.setattr(socket, "getaddrinfo", unavailable)
    settings = SimpleNamespace(
        av_scan_enabled=True, av_host="clamav", av_port=3310, av_timeout_seconds=1
    )
    with pytest.raises(HTTPException) as error:
        scan_upload(b"synthetic content", settings)
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "ANTIVIRUS_UNAVAILABLE"


def test_antivirus_disabled_is_explicit_not_scanned():
    assert (
        scan_upload(b"fixture", SimpleNamespace(av_scan_enabled=False))["status"] == "not_enabled"
    )


def test_empty_optional_model_paths_do_not_load_current_directory():
    settings = Settings(paddle_model_dir="", quality_embedding_model_dir="")
    assert settings.paddle_model_dir is None
    assert settings.quality_embedding_model_dir is None
    from app.ai.quality.runtime import quality_options

    assert "embedding_provider" not in quality_options(settings, {})
