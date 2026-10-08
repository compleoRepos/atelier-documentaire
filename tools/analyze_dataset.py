#!/usr/bin/env python3
"""Inventaire local du Golden Dataset, sans modifier catalog.json ni appeler de service externe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Analyse locale du dataset documentaire")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    root = args.root.resolve()
    catalog = json.loads((root / "dataset/metadata/catalog.json").read_text(encoding="utf-8"))
    docs = catalog.get("documents", [])
    rows = []
    missing = []
    total_pages = 0
    for item in docs:
        candidates = list((root / "dataset/input").glob(item.get("filename", "")))
        source = candidates[0] if candidates else None
        row = {
            "document_id": item.get("document_id"),
            "filename": item.get("filename"),
            "catalog_pages": item.get("pages"),
            "exists": bool(source),
        }
        if not source:
            missing.append(row["document_id"])
            rows.append(row)
            continue
        row["bytes"] = source.stat().st_size
        row["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        if source.suffix.lower() == ".pdf":
            try:
                import fitz

                d = fitz.open(str(source))
                row["actual_pages"] = len(d)
                row["dimensions"] = [[round(p.rect.width, 2), round(p.rect.height, 2)] for p in d]
                d.close()
            except Exception as exc:
                row["error"] = str(exc)
        else:
            row["actual_pages"] = 1
        total_pages += int(row.get("actual_pages", 0))
        rows.append(row)
    report = {
        "catalog_documents": len(docs),
        "input_documents": sum(x["exists"] for x in rows),
        "total_pages": total_pages,
        "expected_pages": sum(int(x.get("pages") or 0) for x in docs),
        "missing": missing,
        "documents": rows,
        "reference_status": catalog.get("reference_status_summary"),
    }
    out = args.json or root / "test-report" / "dataset-analysis.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
