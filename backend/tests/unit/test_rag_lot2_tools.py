"""Outils de recette du LOT 2 : corpus synthétique, évaluation objective, paquet d'annotation."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load("rag_lot2_corpus")
ev = _load("rag_lot2_eval")


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus")
    gen.build(out)
    return out


def test_corpus_is_deterministic_complete_and_synthetic(corpus, tmp_path):
    again = tmp_path / "again"
    gen.build(again)
    files = sorted(p.relative_to(corpus) for p in corpus.rglob("*") if p.is_file())
    assert files == sorted(p.relative_to(again) for p in again.rglob("*") if p.is_file())
    for rel in files:
        assert (corpus / rel).read_bytes() == (again / rel).read_bytes(), rel
    docs = sorted((corpus / "docs").glob("*.json"))
    assert len(docs) == 8 * 5
    pairs = {}
    for path in sorted((corpus / "expected").glob("*.json")):
        exp = json.loads(path.read_text(encoding="utf-8"))
        pairs.setdefault(f"{exp['source_language']}>{exp['target_language']}", set()).add(
            exp["category"]
        )
        assert exp["terms"] and exp["numbers"] and exp["reference_candidate"]
    assert set(pairs) == {"en>fr", "ar>fr", "es>fr", "de>fr", "fr>en"}
    assert all(len(categories) == 8 for categories in pairs.values())
    blob = "\n".join(p.read_text(encoding="utf-8") for p in corpus.rglob("*") if p.is_file())
    assert "/home/" not in blob and "http" not in blob.replace("http://www.w3.org", "")


def test_expected_surfaces_are_in_clean_sources(corpus):
    for path in sorted((corpus / "expected").glob("*.json")):
        exp = json.loads(path.read_text(encoding="utf-8"))
        if exp["simulated_ocr_noise"]:
            continue
        ir = json.loads((corpus / "docs" / path.name).read_text(encoding="utf-8"))["ir"]
        texts = {b["id"]: b["text"] for page in ir["pages"] for b in page["blocks"]}
        for item in exp["terms"]:
            assert ev.norm(item["surface"]) in ev.norm(texts[item["block"]]), (path.name, item)


def test_referential_holds_deliberate_ambiguity_and_sibling_domain(corpus):
    with (corpus / "referential.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    assert rows and {r["source_language"] for r in rows} == {"en", "ar", "es", "de", "fr"}
    provenance = [r["provenance"] for r in rows]
    assert any(p.endswith("-ambigu") for p in provenance)
    assert any(p.endswith("-domaine-frere") for p in provenance)
    assert {r["domain"] for r in rows} <= {
        "HR", "PAYROLL", "LEGAL", "NOTARIAL", "BANKING", "FINANCE", "TAX", "INSURANCE",
        "ADMINISTRATION", "ACADEMIC", "",
    }  # fmt: skip


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("EUR 3 250,00", True),
        ("3,250.00 EUR", True),
        ("٣٢٥٠٫٠٠ يورو", True),
        ("EUR 3250", False),
        ("EUR 3 520,00", False),
    ],
)
def test_amount_check(text, ok):
    item = {"slot": "A1", "kind": "amount"}
    assert ev.check_number(item, {"amounts": {"A1": 3250.0}}, text, "fr") is ok


@pytest.mark.parametrize(
    ("text", "ok"),
    [
        ("le 17/03/2026", True),
        ("le 17.03.2026", True),
        ("le 17 mars 2026", True),
        ("2026-03-17", True),
        ("le ١٧/٠٣/٢٠٢٦", True),
        ("le 03/17/2026", False),
        ("le 17/03/2025", False),
    ],
)
def test_date_check(text, ok):
    item = {"slot": "D", "kind": "date"}
    assert ev.check_number(item, {"dates": {"D": [17, 3, 2026]}}, text, "fr") is ok


def test_identifier_and_text_helpers():
    item = {"slot": "IBAN", "kind": "id"}
    values = {"ids": {"IBAN": "XX00 TEST 0000 0000 0042 1977"}}
    assert ev.check_number(item, values, "IBAN : XX00TEST000000000042 1977", "fr")
    assert not ev.check_number(item, values, "IBAN : XX00 TEST 0000 0000 0042 1979", "fr")
    assert ev.norm("L\u2019employeur\u00a0 ") == "l'employeur"
    assert ev.chrf("bulletin de paie", "bulletin de paie") == 100.0
    assert ev.chrf("", "bulletin de paie") == 0.0
    assert 0 < ev.chrf("bulletin de salaire", "bulletin de paie") < 100


@pytest.mark.parametrize(
    ("source", "translation", "added"),
    [
        ("Gehalt 3.250,00 EUR seit 17.03.2026", "salaire 3 250,00 EUR depuis le 17/03/2026", 0),
        ("\u0663\u0662\u0665\u0660\u066b\u0660\u0660", "3 250,00", 0),
        ("salary EUR 3,250.00", "salaire 3 520,00 EUR", 1),
        ("18 weeks", "18 semaines, soit 126 jours", 1),
    ],
)
def test_added_numbers_signal(source, translation, added):
    assert ev.added_numbers(source, translation) == added


def _fake_run(corpus: Path, tmp_path: Path, variants=("A", "C")):
    dumps = tmp_path / "dumps"
    dumps.mkdir()
    documents = []
    for path in sorted((corpus / "expected").glob("*.json")):
        exp = json.loads(path.read_text(encoding="utf-8"))
        name = exp["document"]
        for variant in variants:
            payload = {"translations": exp["reference_candidate"], "issues": []}
            (dumps / f"{name}.{variant}.json").write_text(json.dumps(payload), encoding="utf-8")
        documents.append(
            {
                "document": name,
                "comparison": {"B_identical_to_A": None, "C_blocks_changed": 0},
                "variants": {
                    v: {"decision": "INJECTED" if v == "C" else "UNCHANGED_DISABLED"}
                    for v in variants
                },
            }
        )
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"documents": documents}), encoding="utf-8")
    return dumps, report


def test_evaluation_of_reference_like_output_is_perfect_on_objective_checks(corpus, tmp_path):
    dumps, report = _fake_run(corpus, tmp_path)
    result = ev.evaluate(corpus / "expected", dumps, [report], None)
    summary = result["aggregates"]["by_variant"]["C"]
    assert summary["documents"] == 40 and summary["translated"] == 40
    assert summary["numbers_rate"] == 1.0
    assert summary["terms_strict_rate"] == 1.0
    respected, total = map(int, summary["glossary_respected"].split("/"))
    assert total > 0 and respected == total
    assert summary["chrf_proxy_mean"] == 100.0
    assert summary["abnormal_length_blocks"] == 0
    assert summary["added_numbers"] == 0
    consistent, repeated = map(int, summary["repeated_terms_consistent"].split("/"))
    assert repeated > 0 and consistent == repeated
    assert "NON MESURÉE" in result["aggregates"]["notice"]
    blob = json.dumps(result["aggregates"], ensure_ascii=False)
    sample = json.loads((corpus / "expected" / "paie-en-fr.json").read_text(encoding="utf-8"))
    assert all(text not in blob for text in sample["reference_candidate"].values())


def test_annotation_pack_is_blind_and_complete(corpus, tmp_path):
    dumps, _ = _fake_run(corpus, tmp_path)
    info = ev.annotation_pack(corpus / "expected", dumps, tmp_path / "pack", seed=7)
    assert info["documents"] == 40
    with (tmp_path / "pack" / "pack.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    assert len(rows) == info["rows"]
    assert {r["translation_label"] for r in rows} == {"X", "Y"}
    assert "A" not in {r["translation_label"] for r in rows}
    key = json.loads((tmp_path / "pack" / "key.json").read_text(encoding="utf-8"))
    assert all(sorted(v.values()) == ["A", "C"] for v in key.values())
    assert len({tuple(sorted(v.items())) for v in key.values()}) == 2  # les deux tirages existent


def test_outputs_inside_repository_are_refused(corpus, tmp_path):
    common = ["--expected", str(corpus / "expected"), "--translations", str(tmp_path)]
    common += ["--report", str(tmp_path / "r.json")]
    with pytest.raises(SystemExit):
        ev.main([*common, "--out", str(ROOT / "eval.json")])
    runner = _load("rag_corpus_run")
    base = ["--input", str(corpus / "docs"), "--out-dir", str(tmp_path / "o"), "--tenant-id", "t"]
    with pytest.raises(SystemExit, match="hors du dépôt"):
        runner.main([*base, "--translate", "--dump-translations", str(ROOT / "dump")])
    with pytest.raises(SystemExit, match="exige --translate"):
        runner.main([*base, "--dump-translations", str(tmp_path / "dump")])


def test_untranslated_documents_count_in_plan_but_not_in_output_quality():
    ev = _load("rag_lot2_eval")
    base = {
        "glossary": {"total": 1, "respected": 1, "rag_injected": 0},
        "consistency": {"repeated_terms": 1, "all_correct": 1},
        "numbers": {"amount_ok": 2, "amount_total": 2},
        "withheld": {"ambiguous_injected": 0, "sibling_injected": 0},
    }
    translated = {
        **base,
        "translated": True,
        "terms": {"total": 2, "strict": 2, "folded": 2},
        "selection": {"expected": 2, "injected": 2, "complied": 2},
    }
    plan_only = {
        **base,
        "translated": False,
        "terms": {"total": 2, "strict": 0, "folded": 0},
        "selection": {"expected": 2, "injected": 0, "complied": 0},
        "numbers": {"amount_ok": 0, "amount_total": 2},
    }
    summary = ev.summarize([translated, plan_only])
    assert summary["documents"] == 2 and summary["translated"] == 1
    assert summary["terms_total"] == 2 and summary["terms_strict_rate"] == 1.0
    assert summary["numbers_ok"] == "2/2" and summary["glossary_respected"] == "1/1"
    assert summary["model_compliance"] == 1.0
    assert summary["plan_selection_recall"] == 0.5  # le plan RAG compte pour les deux
    assert ev.summarize([plan_only])["terms_strict_rate"] is None
