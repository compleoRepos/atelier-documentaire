"""Tests unitaires du bornage de contexte privé.

Ces tests n'importent aucun modèle : le tokenizer est un double local déterministe.
"""

from __future__ import annotations

import json

import pytest

from app.ai.context.builder import ContextPackBuilder


class CharTokenizer:
    """Tokenizer local qui compte exactement les caractères sérialisés."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def encode(self, value: str, *, add_special_tokens: bool = False) -> list[int]:
        self.calls.append((value, add_special_tokens))
        return list(range(len(value)))


class WordTokenizer:
    def encode(self, value: str, *, add_special_tokens: bool = False) -> list[int]:
        return value.split()


def block(block_id: str, text: str, page: int = 1, language: str = "en") -> dict:
    return {"id": block_id, "text": text, "page": page, "language": language}


def ir_with(*blocks: dict, tables: list[dict] | None = None) -> dict:
    pages: dict[int, list[dict]] = {}
    for item in blocks:
        pages.setdefault(int(item.get("page", 1)), []).append(item)
    return {
        "schema_version": "1",
        "language": "en",
        "domain": "employment",
        "pages": [{"number": page, "blocks": values} for page, values in sorted(pages.items())],
        "tables": tables or [],
    }


def test_count_tokens_uses_injected_local_tokenizer_without_download() -> None:
    tokenizer = CharTokenizer()
    builder = ContextPackBuilder(tokenizer=tokenizer, max_tokens=100)

    assert builder.count_tokens("abc") == len(str([{"role": "user", "content": "abc"}]))
    assert tokenizer.calls[-1][1] is False


def test_negative_or_zero_context_budget_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        ContextPackBuilder(max_tokens=0)
    with pytest.raises(ValueError, match="positive"):
        ContextPackBuilder(max_tokens=-1)


def test_units_are_page_ordered_and_keep_regular_paragraphs_atomic() -> None:
    document = ir_with(block("p2", "page two", 2), block("p1", "page one", 1))

    units = ContextPackBuilder(tokenizer=WordTokenizer()).units(document)

    assert [(unit.page, unit.kind, unit.block_ids) for unit in units] == [
        (1, "paragraph", ("p1",)),
        (2, "paragraph", ("p2",)),
    ]


def test_table_with_cells_spread_across_pages_is_one_atomic_unit() -> None:
    table = {
        "page": 1,
        "cells": [{"block_id": "cell-a"}, {"block_ids": ["cell-b"]}],
    }
    document = ir_with(
        block("cell-a", "first cell", 1),
        block("cell-b", "second cell", 2),
        block("outside", "paragraph", 2),
        tables=[table],
    )

    units = ContextPackBuilder(tokenizer=WordTokenizer()).units(document)

    table_units = [unit for unit in units if unit.kind == "table"]
    assert len(table_units) == 1
    assert set(table_units[0].block_ids) == {"cell-a", "cell-b"}
    assert [unit.block_ids for unit in units] == [
        ("cell-a", "cell-b"),
        ("outside",),
    ]


def test_table_is_never_split_when_it_exceeds_budget() -> None:
    document = ir_with(
        block("a", "cell one", 1),
        block("b", "cell two", 1),
        tables=[{"page": 1, "block_ids": ["a", "b"]}],
    )
    builder = ContextPackBuilder(tokenizer=CharTokenizer(), max_tokens=1)

    chunks = builder.build_chunks(document)

    assert len(chunks) == 1
    assert chunks[0]["overflow"] is True
    assert [item["id"] for item in chunks[0]["blocks"]] == ["a", "b"]


def test_oversized_paragraph_is_reported_as_whole_overflow_not_token_slices() -> None:
    document = ir_with(block("p", "a very long paragraph"))
    builder = ContextPackBuilder(tokenizer=CharTokenizer(), max_tokens=2)

    chunks = builder.build_chunks(document)

    assert chunks[0]["overflow"] is True
    assert len(chunks[0]["blocks"]) == 1
    assert chunks[0]["blocks"][0]["text"] == "a very long paragraph"


def test_small_atomic_units_are_grouped_until_budget_boundary() -> None:
    document = ir_with(block("a", "one"), block("b", "two"))
    # Word tokenizer makes each serialized unit five words; six words cannot fit.
    builder = ContextPackBuilder(tokenizer=WordTokenizer(), max_tokens=26)

    chunks = builder.build_chunks(document)

    assert len(chunks) == 1
    assert all(not chunk["overflow"] for chunk in chunks)
    assert [block["id"] for block in chunks[0]["blocks"]] == ["a", "b"]


def test_missing_block_ids_are_not_emitted_as_context_units() -> None:
    document = {"pages": [{"number": 1, "blocks": [{"text": "ignored"}, block("ok", "kept")]}]}

    units = ContextPackBuilder().units(document)

    assert [unit.block_ids for unit in units] == [("ok",)]


def test_table_without_references_remains_synthetic_and_atomic() -> None:
    document = ir_with(tables=[{"page": 3, "cells": [{"text": "unreferenced"}]}])

    units = ContextPackBuilder(tokenizer=WordTokenizer()).units(document)

    assert len(units) == 1
    assert units[0].kind == "table"
    assert units[0].block_ids[0].startswith("table:")
    assert "unreferenced" in units[0].text


def test_relevant_context_retrieves_only_exact_memory_candidates_and_limits_results() -> None:
    source = block("b", "EmploymentCertificate")
    chunk = {"blocks": [source]}
    memories = {"EmploymentCertificate": "Attestation travail", "Employment": "faux proche"}
    memories.update({f"EmploymentCertificate-{i}": str(i) for i in range(30)})

    context = ContextPackBuilder().relevant_context({}, chunk, {"memory": memories})

    assert context["memory"] == [
        {"source": "EmploymentCertificate", "target": "Attestation travail"}
    ]


def test_list_memory_retrieval_is_exact_and_capped_at_sixteen() -> None:
    chunk = {"blocks": [block("b", "Term")]}
    memory = [{"source": "Term", "target": str(i), "validated": False} for i in range(30)]

    context = ContextPackBuilder().relevant_context({}, chunk, {"memory": memory})

    assert len(context["memory"]) == 16
    assert all(item["source"] == "Term" for item in context["memory"])


def test_relevant_context_has_bounded_categories_and_does_not_dump_full_ir() -> None:
    source = block("b", "contract")
    options = {
        "document_context": [{"summary": "contract"}]
        + [{"summary": "contract"} for _ in range(20)],
        "glossary": [{"source": "contract", "target": "contrat"}]
        + [{"source": "contract", "target": str(i)} for i in range(30)],
        "protected_entities": ["contract"],
        "decisions": [{"decision": "contract"}] * 20,
        "previous": [{"source": "contract", "target": "contrat"}] * 20,
        "memory": {},
    }

    context = ContextPackBuilder().relevant_context(
        {"pages": ["must not leak"]}, {"blocks": [source]}, options
    )

    assert len(context["document"]) <= 8
    assert len(context["terms"]) <= 16
    assert len(context["decisions"]) <= 8
    assert len(context["previous"]) <= 8
    assert "pages" not in json.dumps(context)


def test_pack_contains_document_metadata_source_blocks_and_selected_context_only() -> None:
    source = block("b", "contract")
    chunk = {"pages": [1], "blocks": [source], "units": [], "overflow": False}

    packed = ContextPackBuilder().pack(
        {"schema_version": "v1", "domain": "legal", "language": "en", "pages": ["secret"]},
        chunk,
        {"memory": {"contract": "contrat"}},
    )

    assert packed["document"] == {"schema_version": "v1", "domain": "legal", "language": "en"}
    assert packed["source_blocks"] == [source]
    assert packed["relevant_context"]["memory"] == [{"source": "contract", "target": "contrat"}]
    assert "secret" not in json.dumps(packed)
