"""Modèles légers et sérialisables de l'IR documentaire."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Block:
    id: str
    page: int
    kind: str = "text"
    text: str = ""
    bbox: tuple[float, float, float, float] = (0, 0, 0, 0)
    font_size: float | None = None
    confidence: float = 1.0
    language: str = "unknown"
    provenance: str = "native"
    protected: bool = False
    reading_order: int = 0
    source_ref: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["bbox"] = list(self.bbox)
        return d


@dataclass
class Page:
    number: int
    width: float
    height: float
    scanned: bool
    blocks: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocumentIR:
    schema_version: str = "1.0"
    source_path: str = ""
    format: str = ""
    language: str = "unknown"
    languages: list[str] = field(default_factory=list)
    document_type: str = "unknown"
    domain: str = "unknown"
    pages: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    versions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
