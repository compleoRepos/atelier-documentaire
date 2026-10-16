"""RUN27 scorecard v2 (``scorecard-2``): documentary confidence ``doc-confidence-2``
computed ONLY from produced artefacts.

The v1 extraction (``scorecard.document_components``, frozen for RUN26) is
reused unchanged; v2 then:

* moves the seven v1 evidence sub-components to the evidence GATE;
* adds ``entities.entity_alerts`` (critical entity alerts of the product and
  digit mismatches of the scorecard, per translated block holding an entity)
  and ``entities.names_clauses_verified`` (human, unknown without review);
* adds ``layout.no_critical_layout_alert`` from de-duplicated alert families
  (the product writes some alerts twice and the three "missing text" codes
  overlap: a family counts the max of its codes, by block/page/region).

Output: anonymised JSON (counts, ratios, codes; never text) OUTSIDE the
repository. Usage:

  PYTHONPATH=backend:tools/recette python tools/recette/scorecard_v2.py \
      --metrics M.json --sheets SHEETS_DIR --run run26=DIR --out OUT.json [--review REVIEW.json]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from app.documents import confidence_score_v2 as cs2
from measure_v2 import changed
from scorecard import _load, digit_sequence, document_components

REPO = Path(__file__).resolve().parents[2]
VERSION = "scorecard-2"

ENTITY_CODES = frozenset(
    {
        "PROTECTED_ENTITY_CHANGED",
        "CRITICAL_ENTITY_MODIFIED",
        "HALLUCINATION_ENTITY_MODIFIED",
        "HALLUCINATION_UNIT_CHANGED",
    }
)
# Frozen, tool-local entity detector: the MEASURE must not move when the product
# extractor is changed by a remediation. Digits (amounts, dates, identifiers),
# e-mail addresses, and runs of capitalised words or acronyms (names, bodies).
ENTITY_RE = re.compile(
    r"\d|[\w.+-]+@[\w-]+\.[\w.]+|\b[A-ZÀ-ÖØ-Þ]{2,}\b|\b[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+(?:\s+[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ]+)+"
)


def has_entity(text: str) -> bool:
    return bool(ENTITY_RE.search(text or ""))


# family -> (codes, key that identifies one occurrence)
LAYOUT_FAMILIES: dict[str, tuple[frozenset[str], str]] = {
    "missing_text": (
        frozenset(
            {
                "RENDER_SOURCE_TEXT_MISSING",
                "RENDER_TRANSLATED_TEXT_MISSING",
                "RENDER_TEXT_CLIPPED_OR_MISSING",
            }
        ),
        "count",
    ),
    "oversized_mask": (frozenset({"RENDER_TEXT_MASK_TOO_LARGE", "VISUAL_MASK_TOO_LARGE"}), "page"),
    "overflow": (frozenset({"LAYOUT_OVERFLOW"}), "block_id"),
    "text_over_ink": (frozenset({"SCAN_TEXT_OVER_SOURCE_INK"}), "block_id"),
    "protected_region": (frozenset({"PROTECTED_REGION_CHANGED"}), "region"),
    "unmapped_table": (frozenset({"UNMAPPED_TABLE_CONTENT"}), "issue"),
}


def _key(issue: dict, field: str):
    value = issue.get(field)
    return json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value


def layout_occurrences(issues: list[dict]) -> dict[str, int]:
    """De-duplicated critical layout occurrences per family."""
    out: dict[str, int] = {}
    for family, (codes, field) in LAYOUT_FAMILIES.items():
        selected = [i for i in issues if i.get("severity") == "critical" and i.get("code") in codes]
        if field == "count":
            per_code: Counter = Counter()
            seen = set()
            for i in selected:
                sig = (i["code"], i.get("count"))
                if sig in seen:  # identical duplicate written twice
                    continue
                seen.add(sig)
                per_code[i["code"]] += int(i.get("count") or 1)
            out[family] = max(per_code.values(), default=0)
        elif field == "issue":
            out[family] = len({json.dumps(i, sort_keys=True) for i in selected})
        else:
            out[family] = len({_key(i, field) for i in selected})
    return out


def entity_alerts(run_dir: Path, doc: str) -> tuple[float | str, dict]:
    d = run_dir / doc
    ir = _load(d / "analysis.json")
    tr = _load(d / "translation.json")
    translations = tr.get("translations") or {}
    blocks = [b for p in ir.get("pages", []) for b in p.get("blocks", [])]
    with_entity: set[str] = set()
    flagged: set[str] = set()
    for b in blocks:
        bid = str(b["id"])
        src = str(b.get("text") or "")
        tgt = translations.get(bid)
        if not changed(src, tgt):
            continue
        if has_entity(src):
            with_entity.add(bid)
        if digit_sequence(src) != digit_sequence(tgt) and Counter(digit_sequence(src)) != Counter(
            digit_sequence(tgt)
        ):
            flagged.add(bid)
    unmapped = set()
    for i in tr.get("issues") or []:
        if i.get("severity") != "critical" or i.get("code") not in ENTITY_CODES:
            continue
        if i.get("block_id"):
            flagged.add(str(i["block_id"]))
            with_entity.add(str(i["block_id"]))
        else:  # no block: counted once per distinct alert, conservatively
            unmapped.add(json.dumps({k: v for k, v in i.items() if k != "message"}, sort_keys=True))
    den = len(with_entity) + len(unmapped)
    num = len(flagged) + len(unmapped)
    value = cs2.NOT_APPLICABLE if den == 0 else 1.0 - num / den
    return value, {
        "entity_blocks": len(with_entity),
        "entity_alert_blocks": len(flagged),
        "entity_alerts_unmapped": len(unmapped),
    }


def document_v2(
    run_dir: Path, doc: str, metrics: dict, regions: dict, label: str, review: dict | None
):
    comps, critical, blocking, extra = document_components(run_dir, doc, metrics, regions, label)
    evidence = {k: comps["evidence"].get(k) == 1.0 for k in cs2.EVIDENCE_REQUIREMENTS}
    quality = {k: dict(v) for k, v in comps.items() if k != "evidence"}
    value, ent_counts = entity_alerts(run_dir, doc)
    quality["entities"]["entity_alerts"] = value
    quality["entities"]["names_clauses_verified"] = None
    tr = _load(run_dir / doc / "translation.json")
    occ = layout_occurrences(tr.get("issues") or [])
    render = (metrics.get(doc) or {}).get("render") or {}
    measured = sum(
        int(render.get(k) or 0)
        for k in ("blocks_written", "blocks_partial", "blocks_absent", "blocks_no_tokens")
    )
    total = sum(occ.values())
    quality["layout"]["no_critical_layout_alert"] = (
        cs2.NOT_APPLICABLE if measured == 0 else 1.0 - min(1.0, total / measured)
    )
    human_validated = False
    if review:  # only validated human data may replace an unknown (see human_validation.py)
        for name, comp in (review.get("components") or {}).items():
            dim, key = name.split(".", 1)
            if (dim, key) not in cs2.HUMAN_COMPONENTS:
                raise SystemExit(
                    f"{doc}: la revue ne peut renseigner que des composantes humaines ({name})"
                )
            quality[dim][key] = comp
        human_validated = bool(review.get("document_validated"))
    scored = cs2.score_document(
        quality, evidence, critical, human_validated=human_validated, blocking=blocking
    )
    extra = {
        **extra,
        "layout_alert_occurrences": occ,
        "layout_measured_blocks": measured,
        **ent_counts,
    }
    return {**scored, **extra}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--metrics", required=True, type=Path)
    ap.add_argument("--sheets", required=True, type=Path)
    ap.add_argument("--run", action="append", required=True, help="label=out_dir")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument(
        "--review", type=Path, help="validated human review components (human_validation.py ingest)"
    )
    ap.add_argument("--docs", nargs="*", default=[f"DOC-00{n}" for n in range(1, 9)])
    args = ap.parse_args()
    out = args.out.resolve()
    if REPO == out or REPO in out.parents:
        raise SystemExit("--out doit être hors du dépôt")
    metrics = json.loads(args.metrics.read_text())
    reviews = json.loads(args.review.read_text()) if args.review else {}
    result = {
        "version": VERSION,
        "score_version": cs2.VERSION,
        "metrics_version": metrics.get("version"),
        "runs": {},
    }
    for spec in args.run:
        label, path = spec.split("=", 1)
        run_metrics = (metrics.get("runs") or {}).get(label)
        if run_metrics is None:
            raise SystemExit(f"{label}: absent du fichier de mesure")
        docs = {}
        for doc in args.docs:
            if not (Path(path) / doc).is_dir():
                docs[doc] = None  # absent: counted by score_corpus, never dropped
                continue
            regions = _load(args.sheets / doc / "visual-regions.json")
            review = ((reviews.get("runs") or {}).get(label) or {}).get(doc)
            docs[doc] = document_v2(Path(path), doc, run_metrics, regions, label, review)
        corpus = cs2.score_corpus(docs, args.docs)
        result["runs"][label] = {
            "documents": {k: v or cs2.missing_document() for k, v in docs.items()},
            "corpus": corpus,
        }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True, default=str))
    for label, run in result["runs"].items():
        c = run["corpus"]
        print(f"{label}: score {c['score']} [max {c['score_max']}] plafond {c['ceiling']}")


if __name__ == "__main__":
    main()
