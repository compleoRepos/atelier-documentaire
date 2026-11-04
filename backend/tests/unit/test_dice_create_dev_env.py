"""Version finale DICE : le générateur de configuration de laboratoire ne laisse aucun marqueur."""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "tools" / "create_dev_env.py"


def _generate(target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def _values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def test_no_placeholder_left_and_private_permissions(tmp_path: Path) -> None:
    target = tmp_path / "lab.env"
    result = _generate(target)
    assert result.returncode == 0, result.stderr
    text = target.read_text(encoding="utf-8")
    assert "<generate" not in text
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    values = _values(target)
    token = values["OCR_SURYA_TOKEN"]
    assert len(token) >= 32 and token != "<generate-random-token>"
    # Aucun secret ne doit apparaître sur la sortie standard.
    for key in ("OCR_SURYA_TOKEN", "TRANSLATOR_JWT_SECRET", "POSTGRES_PASSWORD"):
        assert values[key] not in result.stdout


def test_tokens_differ_between_runs(tmp_path: Path) -> None:
    first, second = tmp_path / "a.env", tmp_path / "b.env"
    assert _generate(first).returncode == 0
    assert _generate(second).returncode == 0
    assert _values(first)["OCR_SURYA_TOKEN"] != _values(second)["OCR_SURYA_TOKEN"]


def test_dice_defaults_keep_application_identical(tmp_path: Path) -> None:
    target = tmp_path / "lab.env"
    assert _generate(target).returncode == 0
    values = _values(target)
    assert values["TRANSLATOR_RAG_MODE"] == "DISABLED"
    assert values["TRANSLATOR_RAG_ADMIN_ENABLED"] == "false"
    assert values["TRANSLATOR_OCR_BACKEND"] == "surya"


def test_refuses_to_overwrite_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "lab.env"
    target.write_text("EXISTANT=1\n", encoding="utf-8")
    result = _generate(target)
    assert result.returncode != 0
    assert target.read_text(encoding="utf-8") == "EXISTANT=1\n"
