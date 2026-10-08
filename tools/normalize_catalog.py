"""Normalise uniquement des mesures présentes dans les JSON d'inventaire initial."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    metadata = ROOT / "dataset" / "metadata"
    catalog_path = metadata / "catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for document in catalog["documents"]:
        identity = document["document_id"]
        details = json.loads((metadata / f"{identity}.json").read_text(encoding="utf-8"))
        measurements = next(
            (
                details[key]
                for key in ("file", "file_measurements", "file_metrics")
                if key in details
            ),
            details,
        )
        document["file_size_bytes"] = measurements.get("size_bytes", details.get("file_size_bytes"))
        document["sha256"] = measurements.get("sha256", details.get("sha256"))
        document["metadata_path"] = f"dataset/metadata/{identity}.json"
        document["test_case_path"] = f"dataset/metadata/TC-{identity}.json"
        document["source_language_codes"] = {
            "DOC-001": ["en", "fr", "ar"],
            "DOC-002": ["it"],
            "DOC-003": ["fr"],
            "DOC-004": ["nl", "ar"],
            "DOC-005": ["fr"],
            "DOC-006": ["en", "fr"],
            "DOC-007": ["es"],
            "DOC-008": ["de", "fr", "ar"],
        }[identity]
        document["target_language"] = "fr"
        document["language_evidence"] = "initial_visual_observation_not_human_validated"
        if identity == "DOC-001":
            document["images"] = {
                "count_by_page": [58, 27],
                "detail": "Références image PDF, pas illustrations distinctes.",
            }
        elif identity == "DOC-003":
            document["page_format"] = "595.32 × 841.92 points"
            document["images"] = {
                "count_by_page": [110],
                "detail": "Blocs image raster en bandes, pas illustrations distinctes.",
            }
        elif identity == "DOC-005":
            document["page_format"] = "595.32 × 841.92 points sur les deux pages"
            document["images"] = {
                "count_by_page": [110, 110],
                "detail": "Occurrences image PDF, pas illustrations distinctes.",
            }
        elif identity == "DOC-007":
            document["tables"]["pymupdf_detected"] = None
            document["tables"]["detail"] += "; détection programmatique non établie (unknown)"
    catalog["total_pages"] = sum(d["pages"] for d in catalog["documents"])
    catalog["total_size_bytes"] = sum(d["file_size_bytes"] for d in catalog["documents"])
    catalog["source_scope"] = (
        "Observations et mesures des huit JSON DOC ; consolidation déterministe sans nouvelle interprétation."
    )
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "documents": catalog["document_count"],
                "pages": catalog["total_pages"],
                "size_bytes": catalog["total_size_bytes"],
            }
        )
    )


if __name__ == "__main__":
    main()
