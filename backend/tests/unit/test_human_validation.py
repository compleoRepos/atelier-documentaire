"""RUN27: human validation pack (synthetic run directories only, no real data)."""

import csv
import json
import sys
from pathlib import Path

import pytest

TOOLS = str(Path(__file__).resolve().parents[3] / "tools" / "recette")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import human_validation as hv  # noqa: E402

from app.documents import confidence_score_v2 as cs  # noqa: E402

SOURCES = {
    "p001-b0001": ("Fattura numero 4521 del 3 marzo", "Facture numéro 4521 du 3 mars"),
    "p001-b0002": ("Il cliente paga entro trenta giorni", "Le client paie sous trente jours"),
    "p001-b0003": ("12", "12"),
}


def _run(tmp: Path, label: str, scanned=True, altered=None) -> Path:
    doc = tmp / label / "DOC-900"
    doc.mkdir(parents=True)
    blocks = [
        {
            "id": bid,
            "page": 1,
            "text": src,
            "bbox": [10, 10 + i * 20, 200, 25 + i * 20],
            "confidence": 0.9,
            "reading_order": i,
        }
        for i, (bid, (src, _)) in enumerate(SOURCES.items())
    ]
    translations = {bid: tgt for bid, (_, tgt) in SOURCES.items()}
    if altered:
        translations.update(altered)
    status = {
        "p001-b0001": "TRANSLATED",
        "p001-b0002": "TRANSLATED",
        "p001-b0003": "NOT_TRANSLATABLE",
    }
    (doc / "analysis.json").write_text(
        json.dumps({"pages": [{"number": 1, "scanned": scanned, "blocks": blocks}]})
    )
    (doc / "translation.json").write_text(
        json.dumps({"translations": translations, "block_status": status, "issues": []})
    )
    return tmp / label


def _pack(tmp: Path) -> Path:
    ref = _run(tmp, "run27")
    old = _run(tmp, "run26", altered={"p001-b0002": "Le client paie sous trois jours"})
    pack = tmp / "pack"
    hv.export(("run27", ref), [("run26", old)], pack, ["DOC-900"])
    return pack


def _rows(pack: Path) -> list[dict]:
    with (pack / "review-DOC-900.csv").open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _write(pack: Path, rows: list[dict]) -> None:
    with (pack / "review-DOC-900.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _authorise(pack: Path) -> None:
    reviewer = {
        "reviewer_id": "REV-TEST-1",
        "role": "traducteur assermenté (fictif)",
        "languages": ["it", "fr"],
        "authorized_by": "donneur d'ordre (test)",
        "authorization_ref": "AUTH-TEST",
        "authorized_at": "2026-01-01T00:00:00Z",
        "documents": ["DOC-900"],
    }
    (pack / "reviewers.json").write_text(
        json.dumps({"version": hv.VERSION, "reviewers": [reviewer]})
    )


def test_export_is_private_and_starts_with_nobody_authorised(tmp_path):
    pack = _pack(tmp_path)
    rows = _rows(pack)
    assert [r["block_id"] for r in rows] == list(SOURCES)
    assert rows[2]["translation_required"] == "NON" and rows[0]["entity_review_required"] == "OUI"
    assert rows[1]["target_run26"] == "Le client paie sous trois jours"
    assert json.loads((pack / "reviewers.json").read_text())["reviewers"] == []
    with pytest.raises(SystemExit):
        hv.export(("run27", tmp_path / "run27"), [], hv.REPO / "reports" / "x", ["DOC-900"])


def test_empty_pack_keeps_every_human_component_unknown(tmp_path):
    pack = _pack(tmp_path)
    result = hv.ingest(pack, tmp_path / "review.json")
    doc = result["runs"]["run27"]["DOC-900"]
    assert doc["components"] == {} and doc["document_validated"] is False
    assert len(doc["unknown_components"]) == 4
    assert result["status"]["DOC-900"]["state"] == "NOT_STARTED"


def test_unauthorised_reviewer_or_edited_source_is_refused(tmp_path):
    pack = _pack(tmp_path)
    rows = _rows(pack)
    rows[0].update(
        ocr_decision="EXACT", reviewer_id="REV-TEST-1", reviewed_at="2026-02-01T10:00:00Z"
    )
    _write(pack, rows)
    with pytest.raises(SystemExit, match="non autorisé"):
        hv.ingest(pack, tmp_path / "review.json")
    _authorise(pack)
    rows[0]["source_text"] = rows[0]["source_text"] + " (modifié)"
    _write(pack, rows)
    with pytest.raises(SystemExit, match="source modifié"):
        hv.ingest(pack, tmp_path / "review.json")


def test_review_before_authorisation_or_unknown_decision_is_refused(tmp_path):
    pack = _pack(tmp_path)
    _authorise(pack)
    rows = _rows(pack)
    rows[0].update(
        ocr_decision="EXACT", reviewer_id="REV-TEST-1", reviewed_at="2025-12-31T10:00:00Z"
    )
    _write(pack, rows)
    with pytest.raises(SystemExit, match="antérieure"):
        hv.ingest(pack, tmp_path / "review.json")
    rows[0].update(reviewed_at="2026-02-01T10:00:00Z", translation_decision_run27="PERFECT")
    _write(pack, rows)
    with pytest.raises(SystemExit, match="valeur inconnue"):
        hv.ingest(pack, tmp_path / "review.json")


def test_partial_validation_gives_honest_intervals_and_no_document_validation(tmp_path):
    pack = _pack(tmp_path)
    _authorise(pack)
    rows = _rows(pack)
    # only the first block is reviewed: OCR exact, RUN27 accepted, RUN26 identical target accepted
    rows[0].update(
        ocr_decision="EXACT",
        translation_decision_run27="ACCEPT",
        hallucination_run27="NONE",
        entities_run27="OK",
        translation_decision_run26="ACCEPT",
        reviewer_id="REV-TEST-1",
        reviewed_at="2026-02-01T10:00:00Z",
    )
    _write(pack, rows)
    result = hv.ingest(pack, tmp_path / "review.json")
    comps = result["runs"]["run27"]["DOC-900"]["components"]
    chars = [len(s) for s, _ in SOURCES.values()]
    share_tr = chars[0] / (chars[0] + chars[1])
    assert comps["translation.semantic_accuracy"]["lower"] == pytest.approx(share_tr)
    assert comps["translation.semantic_accuracy"]["upper"] == pytest.approx(1.0)
    assert comps["ocr.character_accuracy"]["validated_share"] == pytest.approx(
        chars[0] / sum(chars)
    )
    assert result["runs"]["run27"]["DOC-900"]["document_validated"] is False
    assert result["status"]["DOC-900"]["state"] == "IN_PROGRESS"
    # the interval is accepted by the v2 engine as a partial (never a point) value
    perfect = {n: {k: 1.0 for k in s["components"]} for n, s in cs.DIMENSIONS.items()}
    perfect["translation"]["semantic_accuracy"] = comps["translation.semantic_accuracy"]
    scored = cs.score_document(perfect, {k: True for k in cs.EVIDENCE_REQUIREMENTS})
    assert scored["partial_components"] and scored["status"] == "REVIEW_REQUIRED"


def test_full_review_with_signoff_validates_and_scores_divergences(tmp_path):
    pack = _pack(tmp_path)
    _authorise(pack)
    rows = _rows(pack)
    common = {"reviewer_id": "REV-TEST-1", "reviewed_at": "2026-02-01T10:00:00Z"}
    rows[0].update(
        ocr_decision="EXACT",
        translation_decision_run27="ACCEPT",
        hallucination_run27="NONE",
        entities_run27="OK",
        translation_decision_run26="ACCEPT",
        hallucination_run26="NONE",
        entities_run26="OK",
        **common,
    )
    rows[1].update(
        ocr_decision="CORRECTED",
        reference_transcription="Il cliente paga entro trenta giorni.",
        translation_decision_run27="ACCEPT",
        hallucination_run27="NONE",
        entities_run27="NO_ENTITY",
        translation_decision_run26="MAJOR",  # "trois" instead of "trente"
        hallucination_run26="NONE",
        entities_run26="NO_ENTITY",
        **common,
    )
    rows[2].update(ocr_decision="EXACT", entities_run27="OK", entities_run26="OK", **common)
    _write(pack, rows)
    (pack / "signoff.json").write_text(
        json.dumps(
            {
                "version": hv.VERSION,
                "signoffs": [
                    {
                        "doc": "DOC-900",
                        "run": "run27",
                        "decision": "VALIDATED",
                        "reviewer_id": "REV-TEST-1",
                    }
                ],
            }
        )
    )
    result = hv.ingest(pack, tmp_path / "review.json")
    r27, r26 = result["runs"]["run27"]["DOC-900"], result["runs"]["run26"]["DOC-900"]
    assert (
        r27["document_validated"] is True and r26["document_validated"] is False
    )  # no RUN26 sign-off
    assert r27["components"]["translation.semantic_accuracy"]["lower"] == pytest.approx(1.0)
    assert r26["components"]["translation.semantic_accuracy"]["lower"] < 1.0
    assert r27["components"]["ocr.character_accuracy"]["lower"] < 1.0  # one missing full stop
    journal = (pack / "divergences.jsonl").read_text().splitlines()
    assert len(journal) == 3 and all(json.loads(j)["reviewer_id"] == "REV-TEST-1" for j in journal)
