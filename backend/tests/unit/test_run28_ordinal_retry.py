"""RUN28 F41 regression tests (synthetic data only, no corpus text).

The F34 ordinal guard (RUN27) refused the same model answer on four corpus
runs in a row: the model wrote the French ordinal suffix after a number other
than 1, and the translation memory sent the refused block again on every run.
F41: the service retries such a block ONCE with a dedicated instruction; a
block refused again keeps its source, goes to review and carries a versioned
GUARD_RETRY_EXHAUSTED marker; the translation memory then reuses that visible
refusal instead of sending the block to the model again and again.

F42 — once the retry produced a correct translation, the entity check raised
two critical "extra number" alerts: digits written with an ordinal suffix
("21st", "1er") were never extracted as numbers, their plain translation ("21")
was. Ordinal day/rank numbers are now the same number on both sides; real
modifications and omissions stay critical (pinned below).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx
import pytest
from test_interim_owner_authorization import options
from test_interim_unchanged_retry import _ir, _response

from app.ai.translation import service
from app.documents.block_status import classify_blocks

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import interim_owner_corpus_run as launcher  # noqa: E402

SOURCE = "Season from 2nd March to 21st February"
GOOD = "Saison du 2 mars au 21 février"
NEIGHBOUR = {"id": "w1", "text": "Employment certificate", "language": "eng"}
BLOCKS = [{"id": "o1", "text": SOURCE, "language": "eng"}, NEIGHBOUR]
_PLACEHOLDER = re.compile(r"⟦[^⟧]+⟧")


def _ordinal_handler(seen: list[dict], fix_on_retry: bool):
    def handler(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        blocks = json.loads(body["messages"][1]["content"])["blocks"]
        retry = "wrote a French ordinal suffix" in system
        seen.append({"ids": [b["id"] for b in blocks], "ordinal_retry": retry})
        out = []
        for b in blocks:
            if b["id"] == "o1":
                first, second = _PLACEHOLDER.findall(b["text"])
                suffix = "" if retry and fix_on_retry else "er"
                out.append((b["id"], f"Saison du {first} mars au {second}{suffix} février"))
            else:
                out.append((b["id"], "Certificat de travail"))
        return _response(out)

    return handler


async def _run(tmp_path, fix_on_retry):
    seen: list[dict] = []
    result = await service.translate_blocks(
        _ir([dict(b) for b in BLOCKS]),
        options(tmp_path, httpx.MockTransport(_ordinal_handler(seen, fix_on_retry))),
    )
    return seen, result


def _status(target, issues):
    block = dict(BLOCKS[0])
    ir = {"languages": ["fra", "eng"], "pages": [{"number": 1, "blocks": [block]}]}
    return classify_blocks(ir, {"o1": target}, issues)["blocks"]["o1"]


@pytest.mark.asyncio
async def test_invalid_ordinal_is_retried_once_and_applied_when_fixed(tmp_path):
    seen, result = await _run(tmp_path, fix_on_retry=True)
    assert [s["ordinal_retry"] for s in seen] == [False, True]
    assert seen[1]["ids"] == ["o1"]  # only the refused block, not its neighbour
    assert result["translations"]["o1"] == GOOD
    assert result["translations"]["w1"] == "Certificat de travail"
    codes = [i["code"] for i in result["issues"]]
    assert "TARGET_ORDINAL_RETRY" in codes
    assert "IMPLAUSIBLE_TARGET_ORDINAL" not in codes
    assert "GUARD_RETRY_EXHAUSTED" not in codes
    assert "o1" not in (result.get("untranslated_blocks") or [])
    provenance = result["translation_telemetry"]["block_provenance"]["blocks"]["o1"]
    assert provenance["origin"] == "MODEL_CALL" and provenance["outcome"] == "CHANGED"
    assert provenance["retry_kind"] == "ordinal"
    assert result["translation_telemetry"]["ordinal_retries"] == [{"blocks": 1, "depth": 0}]
    assert _status(result["translations"]["o1"], result["issues"])["status"] == "TRANSLATED"


@pytest.mark.asyncio
async def test_invalid_ordinal_refused_again_keeps_source_and_is_marked_exhausted(tmp_path):
    seen, result = await _run(tmp_path, fix_on_retry=False)
    assert [s["ordinal_retry"] for s in seen] == [False, True]  # bounded: one retry only
    assert result["translations"]["o1"] == SOURCE  # never the implausible target
    refused = [i for i in result["issues"] if i["code"] == "IMPLAUSIBLE_TARGET_ORDINAL"]
    assert [i["block_id"] for i in refused] == ["o1"] and refused[0]["severity"] == "error"
    exhausted = [i for i in result["issues"] if i["code"] == "GUARD_RETRY_EXHAUSTED"]
    assert len(exhausted) == 1 and exhausted[0]["block_id"] == "o1"
    assert exhausted[0]["severity"] == "info"
    assert exhausted[0]["guard"] == "IMPLAUSIBLE_TARGET_ORDINAL"
    assert exhausted[0]["guard_version"] == service.ORDINAL_GUARD_VERSION
    assert "o1" in result["untranslated_blocks"]
    provenance = result["translation_telemetry"]["block_provenance"]["blocks"]["o1"]
    assert provenance["outcome"] == "GUARD_REJECTED" and provenance["retry_kind"] == "ordinal"
    status = _status(result["translations"]["o1"], result["issues"])
    assert (status["status"], status["reason"]) == ("FAILED", "implausible_target")


def test_ordinal_retry_instruction_is_dedicated_and_other_instructions_unchanged():
    ordinal = service._instructions({}, "ordinal")
    assert ordinal.startswith(service._RETRY_ORDINAL_INSTRUCTION)
    assert service._instructions({}, "partial").startswith(service._RETRY_PARTIAL_INSTRUCTION)
    assert service._instructions({}, True).startswith(service._RETRY_UNCHANGED_INSTRUCTION)
    base = service._instructions({}, False)
    assert ordinal.endswith(base) and not base.startswith("In every block")


def _exhausted_issue(version=None, guard="IMPLAUSIBLE_TARGET_ORDINAL"):
    return {
        "code": "GUARD_RETRY_EXHAUSTED",
        "severity": "info",
        "block_id": "o1",
        "guard": guard,
        "guard_version": version or service.ORDINAL_GUARD_VERSION,
    }


_REFUSAL = {"code": "IMPLAUSIBLE_TARGET_ORDINAL", "severity": "error", "block_id": "o1"}


def test_exhausted_blocks_require_current_guard_version_and_the_refusal_itself():
    assert launcher._exhausted_retry_blocks([_REFUSAL, _exhausted_issue()]) == {"o1"}
    # a later guard version must be allowed to look at the block again
    assert (
        launcher._exhausted_retry_blocks([_REFUSAL, _exhausted_issue("ordinal-guard-0")]) == set()
    )
    # the marker alone (refusal not in the cache) is never enough
    assert launcher._exhausted_retry_blocks([_exhausted_issue()]) == set()


def _write_cache(cache_dir: Path, issues: list[dict]) -> None:
    cache_dir.mkdir(parents=True)
    pages = [{"number": 1, "blocks": [dict(b) for b in BLOCKS]}]
    (cache_dir / "analysis.json").write_text(json.dumps({"pages": pages}))
    cached = {
        "translations": {"o1": SOURCE, "w1": "Certificat de travail"},
        "issues": issues,
        "untranslated_blocks": ["o1"],
        "translation_telemetry": {
            "provider": "interim",
            "block_provenance": {
                "blocks": {
                    "o1": {"origin": "MODEL_CALL", "outcome": "GUARD_REJECTED"},
                    "w1": {"origin": "MODEL_CALL", "outcome": "CHANGED"},
                }
            },
        },
    }
    (cache_dir / "interim-service-result.json").write_text(json.dumps(cached))


async def _wrapped(tmp_path, monkeypatch, issues):
    cache_dir = tmp_path / "cache-run" / "out" / "DOC-T"
    _write_cache(cache_dir, issues)
    work = tmp_path / "work"
    work.mkdir()
    sent: list[str] = []

    def fake_translate(reduced, _options):
        ids = [str(b["id"]) for p in reduced["pages"] for b in p["blocks"]]
        sent.extend(ids)
        return {
            "translations": {i: SOURCE for i in ids},
            "issues": [],
            "untranslated_blocks": ids,
            "translation_telemetry": {"provider": "interim", "requests_sent": 1 if ids else 0},
        }

    monkeypatch.setattr(launcher, "_REAL_TRANSLATE_BLOCKS", fake_translate)
    wrapper = launcher._caching_translate(work, cache_dir)
    merged = await wrapper(_ir([dict(b) for b in BLOCKS]), {})
    return sent, merged


@pytest.mark.asyncio
async def test_memory_reuses_an_exhausted_refusal_visibly_instead_of_resending(
    tmp_path, monkeypatch
):
    sent, merged = await _wrapped(tmp_path, monkeypatch, [_REFUSAL, _exhausted_issue()])
    assert sent == []  # neither the refused block nor its accepted neighbour is sent
    memory = merged["translation_telemetry"]["translation_memory"]
    assert memory["refusal_reused_not_resent"] == ["o1"]
    assert memory["invalidated_by_current_guard"] == {}
    assert merged["translations"]["o1"] == SOURCE
    assert "o1" in merged["untranslated_blocks"]
    codes = {i["code"] for i in merged["issues"] if i.get("block_id") == "o1"}
    assert {"IMPLAUSIBLE_TARGET_ORDINAL", "GUARD_RETRY_EXHAUSTED"} <= codes
    provenance = merged["translation_telemetry"]["block_provenance"]["blocks"]["o1"]
    assert provenance["origin"] == "TRANSLATION_MEMORY"
    status = _status(merged["translations"]["o1"], merged["issues"])
    assert (status["status"], status["reason"]) == ("FAILED", "implausible_target")


@pytest.mark.asyncio
async def test_memory_still_resends_a_refusal_without_exhausted_retry(tmp_path, monkeypatch):
    # counter-test: a plain refusal (no targeted retry yet, or an older guard
    # version) is sent again, so the service can make its one retry
    for issues in ([_REFUSAL], [_REFUSAL, _exhausted_issue("ordinal-guard-0")]):
        sent, merged = await _wrapped(tmp_path / str(len(issues)), monkeypatch, issues)
        assert sent == ["o1"]
        memory = merged["translation_telemetry"]["translation_memory"]
        assert memory["invalidated_by_current_guard"] == {"o1": "previous_guard_rejection"}
        assert memory["refusal_reused_not_resent"] == []


@pytest.mark.asyncio
async def test_failed_ordinal_retry_request_keeps_source_with_a_critical_issue(tmp_path):
    seen: list[dict] = []
    inner = _ordinal_handler(seen, fix_on_retry=False)

    def handler(request):
        if "wrote a French ordinal suffix" in json.loads(request.content)["messages"][0]["content"]:
            seen.append({"failed": True})
            return httpx.Response(500, json={"error": "synthetic"})
        return inner(request)

    result = await service.translate_blocks(
        _ir([dict(b) for b in BLOCKS]), options(tmp_path, httpx.MockTransport(handler))
    )
    assert len(seen) == 2 and seen[1] == {"failed": True}
    assert result["translations"]["o1"] == SOURCE  # never the implausible target
    assert "o1" in result["untranslated_blocks"]
    critical = [i for i in result["issues"] if i.get("block_id") == "o1"]
    assert critical and all(i["severity"] == "critical" for i in critical)
    provenance = result["translation_telemetry"]["block_provenance"]["blocks"]["o1"]
    assert provenance["origin"] == "MODEL_CALL_FAILED" and provenance["retry_kind"] == "ordinal"


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("Season from 2nd March to 21st February", "Saison du 2 mars au 21 février"),
        ("Valid from 1st March 2024 to 30th June 2025", "Valable du 1er mars 2024 au 30 juin 2025"),
        ("Paid on 5th of May 2023", "Payé le 5 mai 2023"),
        ("The 3rd item of the 12th list", "Le 3e article de la 12e liste"),
        ("Vigente desde el 1º de marzo", "En vigueur depuis le 1er mars"),
    ],
)
def test_f42_ordinal_numbers_are_the_same_number_on_both_sides(source, target):
    from app.ai.quality.entities import compare_entities

    assert compare_entities(source, target)["errors"] == []


def test_f42_real_number_changes_and_omissions_stay_critical():
    from app.ai.quality.entities import compare_entities

    changed = compare_entities(
        "Season from 2nd March to 21st February", "Saison du 2 mars au 12 février"
    )["errors"]
    assert [(e["code"], e["expected"], e["actual"]) for e in changed] == [
        ("CRITICAL_ENTITY_MODIFIED", "21", "12")
    ]
    missing = compare_entities("Season from 2nd March", "Saison de mars")["errors"]
    assert [(e["code"], e["expected"]) for e in missing] == [("CRITICAL_ENTITY_MISSING", "2")]
    assert all(e["severity"] == "critical" for e in changed + missing)


def test_f42_extracts_the_digits_only_and_never_overlaps_codes():
    from app.ai.quality.entities import extract_entities

    found = extract_entities("from the 21st on")
    assert [(e["type"], e["value"], e["start"], e["end"]) for e in found] == [
        ("number", "21", 9, 11)
    ]
    # three digits and more followed by a letter stay a "code" (unchanged rule)
    assert [(e["type"], e["value"]) for e in extract_entities("Ref 100th")] == [("code", "100th")]
    assert extract_entities("Box 3D and 2B") == []
    assert extract_entities("21stX") == []
