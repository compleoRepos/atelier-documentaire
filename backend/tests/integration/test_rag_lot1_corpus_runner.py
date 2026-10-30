"""DICE (RAG) LOT 1 — fonctionnement réel du lanceur ``tools/rag_corpus_run.py``.

Exécute ``main()`` sur la base de test (deux IR synthétiques) ; aucun réseau :
reconstruction à blanc des requêtes, traduction uniquement avec le moteur offline.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from app.rag.models import RagSearchLog

from .rag_support import make_rag_client, publish_referential

ROOT = Path(__file__).resolve().parents[3]
SECRET_WORDS = ("gross", "notice", "salary", "slip", "employee", "monthly")


def _runner():
    spec = importlib.util.spec_from_file_location(
        "rag_corpus_run", ROOT / "tools/rag_corpus_run.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ir(text_a: str, text_b: str) -> dict:
    return {
        "language": "en",
        "domain": "HR",
        "pages": [
            {
                "number": 1,
                "blocks": [
                    {"id": "b001", "text": text_a, "language": "en"},
                    {"id": "b002", "text": text_b, "language": "en"},
                ],
            }
        ],
    }


def _inputs(tmp_path: Path) -> Path:
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "SYN-001.json").write_text(
        json.dumps(
            {
                "ir": _ir("Gross salary and notice period apply.", "See the monthly pay slip."),
                "options": {
                    "target_language": "fr",
                    "glossary": [{"source": "gross salary", "target": "rémunération brute"}],
                },
            }
        ),
        encoding="utf-8",
    )
    (folder / "SYN-002.json").write_text(
        json.dumps(_ir("The employee signs here.", "Notice period: one month.")), encoding="utf-8"
    )
    return folder


@pytest.fixture
def prepared(app_env, monkeypatch, tmp_path):
    client, app, ids = make_rag_client(monkeypatch, mode="ASSISTED")
    publish_referential(client, ids, max_mode="ASSISTED")
    return app, ids, _inputs(tmp_path)


def test_runner_probe_only_private_engine(prepared, tmp_path, capsys):
    app, ids, folder = prepared
    out = tmp_path / "out-probe"
    code = _runner().main(
        [
            "--input", str(folder), "--out-dir", str(out), "--tenant-id", ids["tenant-a"],
            "--engine", "private", "--target-language", "fr",
        ]
    )  # fmt: skip
    assert code == 0
    report = json.loads((out / "rag-corpus-report.json").read_text(encoding="utf-8"))
    assert report["summary"]["documents"] == 2
    assert report["summary"]["B_identical_to_A_all"] is True
    assert report["summary"]["translated"] is False
    first = {d["document"]: d for d in report["documents"]}["SYN-001"]
    a, b, c = (first["variants"][v] for v in "ABC")
    assert a["decision"] == "UNCHANGED_DISABLED" and a["options_unchanged_object"] is True
    assert b["decision"] == "SHADOW_DISPATCHED" and b["dispatch"] == "inline-logged"
    assert c["decision"] == "INJECTED"
    # Glossaire prioritaire : seuls « notice period » et « pay slip » sont injectés.
    assert len(c["injected_term_ids"]) == 2
    assert c["requests"] == a["requests"]
    assert first["comparison"]["C_requests_identical_to_A"] is False
    assert first["comparison"]["C_prompt_tokens_delta"] > 0
    raw = (out / "rag-corpus-report.json").read_text(encoding="utf-8").lower()
    for word in SECRET_WORDS:
        assert word not in raw
    with app.state.session_factory() as db:
        origins = sorted((row.origin, row.mode) for row in db.query(RagSearchLog).all())
    assert ("corpus", "SHADOW") in origins and ("corpus", "ASSISTED") in origins


def test_runner_translates_with_offline_engine(prepared, tmp_path):
    _, ids, folder = prepared
    out = tmp_path / "out-offline"
    code = _runner().main(
        [
            "--input", str(folder), "--out-dir", str(out), "--tenant-id", ids["tenant-a"],
            "--engine", "offline", "--target-language", "fr", "--translate",
        ]
    )  # fmt: skip
    assert code == 0
    report = json.loads((out / "rag-corpus-report.json").read_text(encoding="utf-8"))
    for document in report["documents"]:
        a, b, c = (document["variants"][v] for v in "ABC")
        assert document["comparison"]["B_identical_to_A"] is True
        assert a["translations_sha256"] == b["translations_sha256"] == c["translations_sha256"]
        # Moteur offline : C plafonné à SHADOW, aucune injection, aucun bloc changé.
        assert c["decision"] == "SHADOW_DISPATCHED"
        assert c["injected_term_ids"] == []
        assert document["comparison"]["C_blocks_changed"] == 0


def test_runner_refusals(prepared, tmp_path):
    _, ids, folder = prepared
    runner = _runner()
    with pytest.raises(SystemExit, match="hors du dépôt"):
        runner.main(
            ["--input", str(folder), "--out-dir", str(ROOT / "tmp-rag-out"),
             "--tenant-id", ids["tenant-a"]]
        )  # fmt: skip
    with pytest.raises(SystemExit, match="allow-model-calls"):
        runner.main(
            ["--input", str(folder), "--out-dir", str(tmp_path / "x"),
             "--tenant-id", ids["tenant-a"], "--engine", "private", "--translate"]
        )  # fmt: skip
    with pytest.raises(SystemExit, match="variants"):
        runner.main(
            ["--input", str(folder), "--out-dir", str(tmp_path / "y"),
             "--tenant-id", ids["tenant-a"], "--variants", "A,D"]
        )  # fmt: skip
    assert not (ROOT / "tmp-rag-out").exists()
