"""Optional-content layer holding the paper-coloured covers written over scanned
source text. Geometry/table detectors ignore it: a cover is translation
evidence, not document structure. A PDF viewer may toggle the layer off to show
the original raster under the translation."""

from __future__ import annotations

from typing import Any

COVER_LAYER = "btp-translation-cover"


def source_drawings(page: Any) -> list[dict[str, Any]]:
    """``page.get_drawings()`` without the renderer's translation covers."""
    try:
        drawings = page.get_drawings()
    except Exception:
        return []
    return [d for d in drawings if d.get("layer") != COVER_LAYER]


def cover_ocg(doc: Any) -> int:
    """Return the xref of the cover layer, creating it once per document."""
    for xref, info in (doc.get_ocgs() or {}).items():
        if info.get("name") == COVER_LAYER:
            return xref
    return doc.add_ocg(COVER_LAYER, on=True)
