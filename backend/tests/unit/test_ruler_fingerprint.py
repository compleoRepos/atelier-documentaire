"""RUN27: the measurement ruler fingerprint covers PRODUCT modules imported by
the measurement tools (lesson: F33 moved historical scores behind an intact
method freeze). Synthetic mini-repository only, no document data."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _tool():
    spec = importlib.util.spec_from_file_location(
        "ruler_fingerprint_under_test", REPO / "tools" / "recette" / "ruler_fingerprint.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mini_repo(root: Path) -> None:
    (root / "backend" / "app" / "rules").mkdir(parents=True)
    (root / "tools" / "recette").mkdir(parents=True)
    (root / "backend" / "app" / "__init__.py").write_text("")
    (root / "backend" / "app" / "rules" / "__init__.py").write_text("")
    (root / "backend" / "app" / "rules" / "status.py").write_text("from app.rules import typo\n")
    (root / "backend" / "app" / "rules" / "typo.py").write_text("KEY = 1\n")
    (root / "backend" / "app" / "unused.py").write_text("X = 0\n")
    (root / "tools" / "recette" / "measure_fake.py").write_text("import app.rules.status\n")


def test_closure_is_transitive_and_ignores_unimported_modules(tmp_path, monkeypatch):
    tool = _tool()
    _mini_repo(tmp_path)
    monkeypatch.setattr(tool, "REPO", tmp_path)
    files = tool.loaded_files(("measure_fake",))
    assert "backend/app/rules/typo.py" in files  # imported through status.py
    assert "backend/app/rules/status.py" in files
    assert "tools/recette/measure_fake.py" in files
    assert "backend/app/unused.py" not in files


def test_product_rule_change_changes_the_ruler(tmp_path, monkeypatch):
    tool = _tool()
    _mini_repo(tmp_path)
    monkeypatch.setattr(tool, "REPO", tmp_path)
    first = tool.fingerprint(("measure_fake",))
    assert tool.fingerprint(("measure_fake",))["ruler_sha256"] == first["ruler_sha256"]
    assert first["product_files"] == 4 and first["tool_files"] == 1
    # A product-only change (the RUN27 F33 situation): tools untouched, ruler differs.
    (tmp_path / "backend" / "app" / "rules" / "typo.py").write_text("KEY = 2\n")
    second = tool.fingerprint(("measure_fake",))
    assert second["ruler_sha256"] != first["ruler_sha256"]
    changed = {a["path"] for a, b in zip(first["files"], second["files"], strict=True) if a != b}
    assert changed == {"backend/app/rules/typo.py"}


def test_real_measurement_ruler_includes_status_and_typography_rules():
    files = _tool().loaded_files(("measure_v2",))
    assert "backend/app/documents/block_status.py" in files
    assert "backend/app/ai/translation/typography.py" in files
    assert "tools/recette/measure_v2.py" in files
