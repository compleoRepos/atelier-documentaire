"""Human validation pack (RUN27, ``human-validation-1``).

Prepares, collects and checks the human references the confidence score cannot
measure by itself: OCR reference transcription of scanned text, verified
reference translation, names/amounts/dates/identifiers/clauses/units check and
addition/omission check. NO validation is ever simulated: an empty pack leaves
every human sub-component unknown (``None``).

Commands (every output must be in the authorised PRIVATE space, never in Git):

  export  --ref LABEL=RUN_DIR [--compare LABEL=RUN_DIR] --out PACK_DIR [--docs ...]
          one CSV per document (UTF-8 BOM, ";" separator, opens in a spreadsheet)
          + manifest.json (row ids and SHA-256 of the source text of each row)
          + reviewers.json / signoff.json templates (empty: nobody is authorised)
  ingest  --pack PACK_DIR --out REVIEW.json
          refuses unknown rows, edited sources, unauthorised reviewers, missing
          dates and out-of-vocabulary decisions; computes, ONLY on validated
          rows, interval sub-components for ``scorecard_v2.py --review`` and a
          private divergence journal (divergences.jsonl).
  status  --pack PACK_DIR      progress per document (counts only)

Interval rule (validated share s of the relevant characters, accuracy a on the
validated part): lower = s * a, upper = s * a + (1 - s). With s = 0 the
sub-component stays unknown; it is never set to a positive value by default.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERSION = "human-validation-1"
DELIM = ";"

OCR_DECISIONS = {"EXACT", "CORRECTED", "ILLEGIBLE"}
TRANSLATION_DECISIONS = {"ACCEPT", "MINOR", "MAJOR", "REJECT"}
HALLUCINATION_DECISIONS = {"NONE", "ADDITION", "OMISSION", "BOTH"}
ENTITY_DECISIONS = {"OK", "KO", "NO_ENTITY"}
NOT_REQUIRED_STATUSES = {"NOT_TRANSLATABLE"}
ENTITY_HINT = re.compile(
    r"\d|@|\b[A-ZÀ-ÖØ-Þ]{2,}\b|\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+"
)

BASE_COLUMNS = [
    "row_id",
    "doc",
    "page",
    "block_id",
    "bbox",
    "scanned_page",
    "ocr_confidence",
    "product_status_{ref}",
    "alerts_{ref}",
    "entity_review_required",
    "translation_required",
    "source_text",
    "target_{ref}",
]
REVIEW_COLUMNS = [
    "ocr_decision",
    "reference_transcription",
    "reference_translation",
    "translation_decision_{run}",
    "hallucination_{run}",
    "entities_{run}",
]
TAIL_COLUMNS = ["reviewer_id", "reviewed_at", "comment"]


def _private(path: Path) -> Path:
    path = path.resolve()
    if path == REPO or REPO in path.parents:
        raise SystemExit("la sortie doit être dans l'espace privé, hors du dépôt")
    return path


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _status(value) -> str:
    return str(value.get("status") if isinstance(value, dict) else value or "")


def _blocks(run_dir: Path, doc: str) -> tuple[dict, dict, dict, dict]:
    ir = _load(run_dir / doc / "analysis.json")
    tr = _load(run_dir / doc / "translation.json")
    scanned = {p["number"]: bool(p.get("scanned")) for p in ir.get("pages", [])}
    blocks = {str(b["id"]): b for p in ir.get("pages", []) for b in p.get("blocks", [])}
    alerts: dict[str, set] = {}
    for issue in tr.get("issues") or []:
        if issue.get("block_id") and issue.get("severity") in ("critical", "error"):
            alerts.setdefault(str(issue["block_id"]), set()).add(str(issue.get("code")))
    return blocks, tr, scanned, alerts


def columns(ref: str, runs: list[str]) -> list[str]:
    cols = [c.format(ref=ref) for c in BASE_COLUMNS]
    cols += [f"target_{r}" for r in runs if r != ref]
    cols += ["ocr_decision", "reference_transcription", "reference_translation"]
    for r in runs:
        cols += [f"translation_decision_{r}", f"hallucination_{r}", f"entities_{r}"]
    return cols + TAIL_COLUMNS


def export(
    ref: tuple[str, Path], compare: list[tuple[str, Path]], out: Path, docs: list[str]
) -> dict:
    out = _private(out)
    out.mkdir(parents=True, exist_ok=True)
    ref_label, ref_dir = ref
    runs = [ref_label] + [label for label, _ in compare]
    cols = columns(ref_label, runs)
    manifest = {
        "version": VERSION,
        "reference_run": ref_label,
        "runs": runs,
        "columns": cols,
        "documents": {},
    }
    for doc in docs:
        blocks, tr, scanned, alerts = _blocks(ref_dir, doc)
        if not blocks:
            manifest["documents"][doc] = {"rows": {}, "missing": True}
            continue
        others = {label: _blocks(path, doc) for label, path in compare}
        rows, meta = [], {}
        statuses = tr.get("block_status") or {}
        for bid, b in sorted(
            blocks.items(),
            key=lambda kv: (kv[1].get("page", 0), kv[1].get("reading_order", 0), kv[0]),
        ):
            src = str(b.get("text") or "")
            if not src.strip():
                continue
            status = _status(statuses.get(bid))
            row_id = f"{doc}:{bid}"
            row = {c: "" for c in cols}
            row.update(
                {
                    "row_id": row_id,
                    "doc": doc,
                    "page": b.get("page"),
                    "block_id": bid,
                    "bbox": json.dumps([round(float(x), 1) for x in b.get("bbox") or []]),
                    "scanned_page": "OUI" if scanned.get(b.get("page")) else "NON",
                    "ocr_confidence": b.get("confidence"),
                    f"product_status_{ref_label}": status,
                    f"alerts_{ref_label}": " ".join(sorted(alerts.get(bid, ()))),
                    "entity_review_required": "OUI" if ENTITY_HINT.search(src) else "NON",
                    "translation_required": "NON" if status in NOT_REQUIRED_STATUSES else "OUI",
                    "source_text": src,
                    f"target_{ref_label}": str((tr.get("translations") or {}).get(bid) or ""),
                }
            )
            for label, (oblocks, otr, _s, _a) in others.items():
                ob = oblocks.get(bid)
                same = ob is not None and _sha(str(ob.get("text") or "")) == _sha(src)
                row[f"target_{label}"] = (
                    str((otr.get("translations") or {}).get(bid) or "") if same else "NON_APPARIÉ"
                )
            rows.append(row)
            meta[row_id] = {
                "source_sha256": _sha(src),
                "chars": len(src),
                "scanned": scanned.get(b.get("page"), False),
                "translation_required": row["translation_required"] == "OUI",
                "entity_review_required": row["entity_review_required"] == "OUI",
                "targets_sha256": {r: _sha(row.get(f"target_{r}", "")) for r in runs},
            }
        with (out / f"review-{doc}.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=cols, delimiter=DELIM)
            writer.writeheader()
            writer.writerows(rows)
        manifest["documents"][doc] = {"rows": meta, "missing": False}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1))
    for name, template in (
        ("reviewers.json", {"version": VERSION, "reviewers": []}),
        ("signoff.json", {"version": VERSION, "signoffs": []}),
    ):
        if not (out / name).exists():  # never overwrite real authorisations
            (out / name).write_text(json.dumps(template, ensure_ascii=False, indent=1))
    return manifest


def _date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _interval(validated: float, total: float, good: float):
    if total <= 0:
        return "NOT_APPLICABLE"
    if validated <= 0:
        return None  # unknown: nothing validated
    share = min(1.0, validated / total)
    accuracy = max(0.0, min(1.0, good / validated))
    low = share * accuracy
    return {"lower": low, "upper": low + (1.0 - share), "validated_share": share}


def ingest(pack: Path, out: Path) -> dict:
    pack, out = _private(pack), _private(out)
    manifest = _load(pack / "manifest.json")
    if manifest.get("version") != VERSION:
        raise SystemExit("manifeste absent ou de version inconnue")
    reviewers = {r["reviewer_id"]: r for r in _load(pack / "reviewers.json").get("reviewers", [])}
    for rid, r in reviewers.items():
        for key in (
            "role",
            "languages",
            "authorized_by",
            "authorization_ref",
            "authorized_at",
            "documents",
        ):
            if not r.get(key):
                raise SystemExit(f"relecteur {rid} : champ d'autorisation manquant ({key})")
    signoffs = _load(pack / "signoff.json").get("signoffs", [])
    runs = manifest["runs"]
    result = {"version": VERSION, "runs": {r: {} for r in runs}, "status": {}}
    journal = []
    for doc, info in manifest["documents"].items():
        meta = info["rows"]
        path = pack / f"review-{doc}.csv"
        reviewed = {}
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh, delimiter=DELIM):
                    rid = row.get("row_id")
                    if rid not in meta:
                        raise SystemExit(f"{doc}: ligne inconnue {rid}")
                    if _sha(row.get("source_text", "")) != meta[rid]["source_sha256"]:
                        raise SystemExit(f"{rid}: texte source modifié dans le fichier de revue")
                    for r in runs:
                        if _sha(row.get(f"target_{r}", "")) != meta[rid]["targets_sha256"][r]:
                            raise SystemExit(f"{rid}: cible {r} modifiée dans le fichier de revue")
                    decisions = [row.get(c, "").strip() for c in sorted(_review_cols(runs))]
                    if not any(decisions):
                        continue
                    reviewer = reviewers.get(row.get("reviewer_id", "").strip())
                    if reviewer is None or doc not in reviewer["documents"]:
                        raise SystemExit(f"{rid}: relecteur non autorisé pour {doc}")
                    when = row.get("reviewed_at", "").strip()
                    if not when or _date(when) < _date(reviewer["authorized_at"]):
                        raise SystemExit(
                            f"{rid}: date de revue absente ou antérieure à l'autorisation"
                        )
                    _check_vocabulary(rid, row, runs)
                    reviewed[rid] = row
                    journal.append(
                        {
                            "row_id": rid,
                            "reviewer_id": reviewer["reviewer_id"],
                            "reviewed_at": when,
                            **{
                                c: row.get(c, "")
                                for c in _review_cols(runs)
                                if row.get(c, "").strip()
                            },
                        }
                    )
        result["status"][doc] = {
            "rows": len(meta),
            "reviewed_rows": len(reviewed),
            "state": "NOT_STARTED"
            if not reviewed
            else ("COMPLETE" if len(reviewed) == len(meta) else "IN_PROGRESS"),
        }
        for r in runs:
            result["runs"][r][doc] = _components(meta, reviewed, r, signoffs, reviewers, doc)
    _private(pack / "divergences.jsonl").write_text(
        "".join(json.dumps(j, ensure_ascii=False) + "\n" for j in journal)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1))
    return result


def _review_cols(runs: list[str]) -> set[str]:
    cols = {"ocr_decision", "reference_transcription", "reference_translation"}
    for r in runs:
        cols |= {f"translation_decision_{r}", f"hallucination_{r}", f"entities_{r}"}
    return cols


def _check_vocabulary(rid: str, row: dict, runs: list[str]) -> None:
    ocr = row.get("ocr_decision", "").strip()
    if ocr and ocr not in OCR_DECISIONS:
        raise SystemExit(f"{rid}: décision OCR inconnue {ocr}")
    if ocr == "CORRECTED" and not row.get("reference_transcription", "").strip():
        raise SystemExit(f"{rid}: CORRECTED sans transcription de référence")
    for r in runs:
        for col, vocab in (
            (f"translation_decision_{r}", TRANSLATION_DECISIONS),
            (f"hallucination_{r}", HALLUCINATION_DECISIONS),
            (f"entities_{r}", ENTITY_DECISIONS),
        ):
            value = row.get(col, "").strip()
            if value and value not in vocab:
                raise SystemExit(f"{rid}: valeur inconnue {col}={value}")
        if (
            row.get(f"translation_decision_{r}", "").strip() == "ACCEPT"
            and not row.get(f"target_{r}", "").strip()
        ):
            raise SystemExit(f"{rid}: ACCEPT sur une cible {r} vide")


def _components(
    meta: dict, reviewed: dict, run: str, signoffs: list, reviewers: dict, doc: str
) -> dict:
    ocr_total = sum(m["chars"] for m in meta.values() if m["scanned"])
    ocr_valid = ocr_good = 0.0
    tr_total = sum(m["chars"] for m in meta.values() if m["translation_required"])
    tr_valid = tr_good = ha_valid = ha_good = 0.0
    en_total = sum(1 for m in meta.values() if m["entity_review_required"])
    en_valid = en_good = 0.0
    for rid, row in reviewed.items():
        m = meta[rid]
        ocr = row.get("ocr_decision", "").strip()
        if m["scanned"] and ocr:
            ref = row["source_text"] if ocr == "EXACT" else row.get("reference_transcription", "")
            ocr_valid += m["chars"]
            if ocr != "ILLEGIBLE":  # illegible: counted as validated with no correct character
                ocr_good += (
                    max(0, len(ref) - _levenshtein(row["source_text"], ref))
                    * m["chars"]
                    / max(len(ref), 1)
                )
        decision = row.get(f"translation_decision_{run}", "").strip()
        if m["translation_required"] and decision:
            tr_valid += m["chars"]
            tr_good += m["chars"] if decision == "ACCEPT" else 0
        hall = row.get(f"hallucination_{run}", "").strip()
        if m["translation_required"] and hall:
            ha_valid += m["chars"]
            ha_good += m["chars"] if hall == "NONE" else 0
        ent = row.get(f"entities_{run}", "").strip()
        if m["entity_review_required"] and ent in ("OK", "KO"):
            en_valid += 1
            en_good += ent == "OK"
        elif m["entity_review_required"] and ent == "NO_ENTITY":
            en_total -= 1  # reviewer states the hint was not an entity
    comps = {
        "ocr.character_accuracy": _interval(ocr_valid, ocr_total, ocr_good),
        "translation.semantic_accuracy": _interval(tr_valid, tr_total, tr_good),
        "hallucination.proven_by_reference": _interval(ha_valid, tr_total, ha_good),
        "entities.names_clauses_verified": _interval(en_valid, en_total, en_good),
    }
    complete = all(
        c == "NOT_APPLICABLE" or (isinstance(c, dict) and c["validated_share"] >= 1.0)
        for c in comps.values()
    )
    signed = any(
        s.get("doc") == doc
        and s.get("run") == run
        and s.get("decision") == "VALIDATED"
        and s.get("reviewer_id") in reviewers
        and doc in reviewers[s["reviewer_id"]]["documents"]
        for s in signoffs
    )
    return {
        "components": {k: v for k, v in comps.items() if v != "NOT_APPLICABLE" and v is not None},
        "unknown_components": sorted(k for k, v in comps.items() if v is None),
        "document_validated": bool(complete and signed),
    }


def status(pack: Path) -> dict:
    manifest = _load(_private(pack) / "manifest.json")
    out = {}
    for doc, info in manifest.get("documents", {}).items():
        path = pack / f"review-{doc}.csv"
        done = 0
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as fh:
                done = sum(
                    1
                    for row in csv.DictReader(fh, delimiter=DELIM)
                    if row.get("reviewer_id", "").strip()
                )
        out[doc] = {"rows": len(info["rows"]), "rows_with_reviewer": done}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--ref", required=True)
    e.add_argument("--compare", action="append", default=[])
    e.add_argument("--out", required=True, type=Path)
    e.add_argument("--docs", nargs="*", default=[f"DOC-00{n}" for n in range(1, 9)])
    i = sub.add_parser("ingest")
    i.add_argument("--pack", required=True, type=Path)
    i.add_argument("--out", required=True, type=Path)
    s = sub.add_parser("status")
    s.add_argument("--pack", required=True, type=Path)
    args = ap.parse_args()
    if args.cmd == "export":
        label, path = args.ref.split("=", 1)
        compare = [(c.split("=", 1)[0], Path(c.split("=", 1)[1])) for c in args.compare]
        m = export((label, Path(path)), compare, args.out, args.docs)
        print({d: len(v["rows"]) for d, v in m["documents"].items()})
    elif args.cmd == "ingest":
        print(json.dumps(ingest(args.pack, args.out)["status"], ensure_ascii=False))
    else:
        print(json.dumps(status(args.pack), ensure_ascii=False))


if __name__ == "__main__":
    main()
