"""Construction bornée de paquets de contexte pour la traduction privée.

Ce module ne fabrique jamais un prompt à partir du document complet. Les unités
(table, paragraphe/bloc) restent atomiques et les éléments de contexte sont
sélectionnés avant le comptage du tokenizer.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextUnit:
    page: int
    block_ids: tuple[str, ...]
    blocks: tuple[dict[str, Any], ...]
    kind: str = "paragraph"

    @property
    def text(self) -> str:
        return "\n".join(str(b.get("text", "")) for b in self.blocks)


@dataclass(frozen=True)
class DocumentMemory:
    """Caller-supplied, tenant-scoped document memory.

    The builder never owns a memory store and never looks one up globally.  A
    caller may pass this small validated projection for the current document;
    only fields useful for retrieval are exposed to a prompt.
    """

    document_type: str | None = None
    domain: str | None = None
    language: str | None = None
    style: str | None = None
    entities: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    terminology: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    translation_decisions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    quality_issues: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> DocumentMemory | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise TypeError("document_memory must be a mapping supplied by the caller")

        def records(key: str) -> tuple[dict[str, Any], ...]:
            raw = value.get(key, ()) or ()
            if isinstance(raw, Mapping):
                raw = [{"source": k, "target": v} for k, v in raw.items()]
            return tuple(dict(item) for item in raw if isinstance(item, Mapping))

        return cls(
            document_type=str(value["document_type"]) if value.get("document_type") else None,
            domain=str(value["domain"]) if value.get("domain") else None,
            language=str(value["language"]) if value.get("language") else None,
            style=str(value["style"]) if value.get("style") else None,
            entities=records("entities"),
            terminology=records("terminology"),
            translation_decisions=records("translation_decisions"),
            quality_issues=records("quality_issues"),
        )


class ContextPackBuilder:
    """Build chunks and relevant, token-bounded context.

    A tokenizer is injected in tests and in deployments. No tokenizer or model
    is downloaded by this class.
    """

    def __init__(self, tokenizer: Any = None, *, max_tokens: int = 22000) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self.tokenizer = tokenizer
        self.max_tokens = max_tokens

    def count_tokens(self, value: Any) -> int:
        """Count serialized content without silently truncating it."""
        if self.tokenizer is None:
            return max(1, len(str(value).split()))
        if isinstance(value, str):
            value = [{"role": "user", "content": value}]
        if hasattr(self.tokenizer, "encode"):
            return len(self.tokenizer.encode(str(value), add_special_tokens=False))
        return max(1, len(str(value).split()))

    def count_messages(self, messages: Sequence[Mapping[str, Any]]) -> int:
        """Count the actual chat-template input when the tokenizer supports it."""
        if self.tokenizer is not None and hasattr(self.tokenizer, "apply_chat_template"):
            rendered = self.tokenizer.apply_chat_template(
                list(messages), tokenize=True, add_generation_prompt=True
            )
            if hasattr(rendered, "shape"):
                return int(rendered.shape[-1])
            try:
                return len(rendered)
            except TypeError:
                return max(1, len(str(rendered).split()))
        return self.count_tokens(list(messages))

    @staticmethod
    def _table_block_ids(table: Mapping[str, Any]) -> set[str]:
        ids: set[str] = set()
        for key in ("block_ids", "blocks"):
            values = table.get(key, [])
            if isinstance(values, Mapping):
                values = values.values()
            for item in values or []:
                if isinstance(item, Mapping):
                    candidate = item.get("id") or item.get("block_id")
                    if candidate is not None:
                        ids.add(str(candidate))
                elif item is not None:
                    ids.add(str(item))
        for cell in table.get("cells", []) or []:
            if not isinstance(cell, Mapping):
                continue
            for key in ("block_id", "id"):
                if cell.get(key) is not None:
                    ids.add(str(cell[key]))
            refs = cell.get("block_ids", []) or []
            ids.update(str(x) for x in refs)
        return ids

    def units(self, ir: Mapping[str, Any]) -> list[ContextUnit]:
        """Return page-ordered atomic table/paragraph units."""
        all_blocks: dict[str, dict[str, Any]] = {}
        pages: dict[int, list[dict[str, Any]]] = {}
        for page in ir.get("pages", []) or []:
            number = int(page.get("number", len(pages) + 1))
            for raw in page.get("blocks", []) or []:
                block = dict(raw)
                if block.get("id") is None:
                    continue
                block["id"] = str(block["id"])
                all_blocks[block["id"]] = block
                pages.setdefault(number, []).append(block)

        table_ids: set[str] = set()
        tables_by_page: dict[int, list[ContextUnit]] = {}
        block_order = {
            str(block["id"]): index
            for index, block in enumerate(block for page in pages.values() for block in page)
        }
        for table in ir.get("tables", []) or []:
            if not isinstance(table, Mapping):
                continue
            ids = self._table_block_ids(table)
            members = [all_blocks[x] for x in ids if x in all_blocks]
            if (
                not members
                and isinstance(table.get("bbox"), (list, tuple))
                and len(table["bbox"]) == 4
            ):
                # Native PDF table detectors supply geometry, not block IDs.
                # Group only actual renderable blocks whose centres lie in the table.
                left, top, right, bottom = [float(value) for value in table["bbox"]]
                for block in pages.get(int(table.get("page") or 1), []):
                    bbox = block.get("bbox")
                    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                        continue
                    centre_x = (float(bbox[0]) + float(bbox[2])) / 2
                    centre_y = (float(bbox[1]) + float(bbox[3])) / 2
                    if left <= centre_x <= right and top <= centre_y <= bottom:
                        members.append(block)
            members.sort(key=lambda block: block_order.get(str(block["id"]), len(block_order)))
            if not members:
                # A table may carry cell text without block references. Keep it
                # atomic as a synthetic unit so it can be reported overflow.
                members = [
                    {
                        "id": f"table:{len(tables_by_page)}",
                        "text": json.dumps(table, ensure_ascii=False),
                    }
                ]
            table_ids.update(str(x.get("id")) for x in members)
            page = int(table.get("page") or members[0].get("page") or 1)
            tables_by_page.setdefault(page, []).append(
                ContextUnit(page, tuple(str(x["id"]) for x in members), tuple(members), "table")
            )

        units: list[ContextUnit] = []
        for page_number in sorted(set(pages) | set(tables_by_page)):
            emitted: set[str] = set()
            for table_unit in tables_by_page.get(page_number, []):
                units.append(table_unit)
                emitted.update(table_unit.block_ids)
            for block in pages.get(page_number, []):
                block_id = str(block["id"])
                if block_id in emitted or block_id in table_ids:
                    continue
                units.append(ContextUnit(page_number, (block_id,), (block,), "paragraph"))
        return units

    def build_chunks(self, ir: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Group whole atomic units under the input budget.

        An individual table or paragraph that exceeds the budget is returned as
        an overflow chunk; it is never cut into arbitrary token slices.
        """
        chunks: list[dict[str, Any]] = []
        current: list[ContextUnit] = []
        current_tokens = 0

        def flush() -> None:
            nonlocal current, current_tokens
            if current:
                chunks.append(self._chunk(current, overflow=False))
                current, current_tokens = [], 0

        for unit in self.units(ir):
            unit_tokens = self.count_tokens(self._unit_json(unit))
            if unit_tokens > self.max_tokens:
                flush()
                chunks.append(self._chunk([unit], overflow=True))
                continue
            if current and current_tokens + unit_tokens > self.max_tokens:
                flush()
            current.append(unit)
            current_tokens += unit_tokens
        flush()
        return chunks

    @staticmethod
    def _unit_json(unit: ContextUnit) -> dict[str, Any]:
        return {"page": unit.page, "kind": unit.kind, "blocks": list(unit.blocks)}

    def _chunk(self, units: Iterable[ContextUnit], *, overflow: bool) -> dict[str, Any]:
        units = list(units)
        blocks = [block for unit in units for block in unit.blocks]
        return {
            "pages": sorted({unit.page for unit in units}),
            "units": [self._unit_json(unit) for unit in units],
            "blocks": blocks,
            "overflow": overflow,
        }

    def relevant_context(
        self,
        ir: Mapping[str, Any],
        chunk: Mapping[str, Any],
        options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Select small relevant context; never serialize the full IR/document."""
        options = options or {}
        source = " ".join(str(b.get("text", "")) for b in chunk.get("blocks", []))
        terms = set(source.lower().split())
        document_memory = DocumentMemory.from_mapping(options.get("document_memory"))
        domain = ir.get("domain") or (document_memory.domain if document_memory else None)

        def domain_matches(item: Any) -> bool:
            """Keep global entries and entries for this document's domain only."""
            if not isinstance(item, Mapping):
                return True
            item_domain = item.get("domain")
            if not item_domain:
                return True
            if not domain:
                return False
            return str(item_domain).strip().casefold() == str(domain).strip().casefold()

        def relevant(items: Any, keys: tuple[str, ...], limit: int = 12) -> list[Any]:
            found: list[Any] = []
            for item in items or []:
                if not domain_matches(item):
                    continue
                if isinstance(item, Mapping):
                    hay = " ".join(str(item.get(k, "")) for k in keys).lower()
                else:
                    hay = str(item).lower()
                if not hay or any(term in hay for term in terms if len(term) > 2):
                    found.append(item)
                if len(found) >= limit:
                    break
            return found

        result: dict[str, Any] = {}
        if document_memory:
            memory_document = {
                key: value
                for key, value in {
                    "document_type": document_memory.document_type,
                    "domain": document_memory.domain,
                    "language": document_memory.language,
                    "style": document_memory.style,
                }.items()
                if value
            }
            if memory_document:
                result["document"] = [memory_document]
            result["document_memory"] = relevant(
                [*document_memory.terminology, *document_memory.translation_decisions],
                ("source", "target", "text", "decision", "domain"),
                16,
            )
        result["document"] = relevant(
            [*result.get("document", []), *options.get("document_context", [])],
            ("text", "summary", "document_type", "domain", "style"),
            8,
        )
        result["terms"] = relevant(
            options.get("terms", options.get("glossary", [])), ("source", "target", "domain"), 16
        )
        result["entities"] = relevant(options.get("protected_entities", []), ("name", "value"), 16)
        result["decisions"] = relevant(options.get("decisions", []), ("decision", "text"), 8)
        previous = options.get("previous_decisions", options.get("previous", []))
        result["previous"] = relevant(previous, ("source", "target", "text", "decision"), 8)

        # Memory is deliberately exact-candidate-only. A memory payload is not
        # a context dump, and validity is supplied by the API, not inferred.
        memory = options.get("memory", {})
        candidates: list[Any] = []
        texts = {str(b.get("text", "")) for b in chunk.get("blocks", [])}
        if isinstance(memory, Mapping):
            candidates = [
                {"source": key, "target": value}
                for key, value in memory.items()
                if str(key) in texts
            ]
        else:
            for item in memory or []:
                if (
                    isinstance(item, Mapping)
                    and item.get("validated") is True
                    and str(item.get("source", "")) in texts
                ):
                    candidates.append(item)
        result["memory"] = candidates[:16]
        return {key: value for key, value in result.items() if value}

    def pack(
        self,
        ir: Mapping[str, Any],
        chunk: Mapping[str, Any],
        options: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        options = options or {}
        return {
            "document": {
                "schema_version": ir.get("schema_version"),
                **(
                    {"document_type": ir["document_type"]}
                    if ir.get("document_type") is not None
                    else {}
                ),
                "domain": ir.get("domain"),
                "language": ir.get("language"),
                **{key: options[key] for key in ("country_context", "style") if options.get(key)},
            },
            "source_blocks": list(chunk.get("blocks", [])),
            "relevant_context": self.relevant_context(ir, chunk, options),
        }
