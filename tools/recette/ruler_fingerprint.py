"""Measurement ruler fingerprint (RUN27, ``ruler-fingerprint-1``).

RUN27 lesson: the method freezes (``METHOD-FREEZE*.sha256``) listed the
measurement TOOLS only, but ``measure_v2.py`` re-derives block statuses with
PRODUCT rules (``block_status``, ``typography``, ``language_evidence`` ...).
A product fix (F33) therefore re-classified historical blocks and moved the
historical scores of one document while every frozen file was intact.

This tool imports the measurement modules in a fresh interpreter and hashes
EVERY repository source file actually loaded (transitive closure), so that two
measurements are declared comparable only when their rulers are identical.

Usage::

    python tools/recette/ruler_fingerprint.py [--out RULER.json]

The output lists repository-relative paths and SHA-256 digests of source code
only (no document data); it may be written anywhere.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VERSION = "ruler-fingerprint-1"
MEASUREMENT_MODULES = (
    "measure_v2",
    "scorecard",
    "scorecard_v2",
    "score_verify",
    "render_outcome",
)

_PROBE = """
import importlib, json, sys
sys.path[:0] = [{backend!r}, {recette!r}]
for name in {modules!r}:
    importlib.import_module(name)
files = sorted({{getattr(m, "__file__", None) or "" for m in list(sys.modules.values())}})
print(json.dumps([f for f in files if f]))
"""


def loaded_files(modules: tuple[str, ...] = MEASUREMENT_MODULES) -> list[str]:
    """Repository-relative ``.py`` files loaded when importing ``modules``."""
    probe = _PROBE.format(
        backend=str(REPO / "backend"), recette=str(REPO / "tools" / "recette"), modules=modules
    )
    out = subprocess.run(
        [sys.executable, "-c", probe], check=True, capture_output=True, text=True, cwd=REPO
    ).stdout
    files = []
    for name in json.loads(out.strip().splitlines()[-1]):
        path = Path(name).resolve()
        if path.suffix == ".py" and REPO in path.parents:
            files.append(path.relative_to(REPO).as_posix())
    return sorted(set(files))


def fingerprint(modules: tuple[str, ...] = MEASUREMENT_MODULES) -> dict:
    entries = []
    for rel in loaded_files(modules):
        digest = hashlib.sha256((REPO / rel).read_bytes()).hexdigest()
        entries.append({"path": rel, "sha256": digest})
    combined = hashlib.sha256(
        "".join(f"{e['sha256']}  {e['path']}\n" for e in entries).encode()
    ).hexdigest()
    product = [e["path"] for e in entries if e["path"].startswith("backend/app/")]
    return {
        "version": VERSION,
        "modules": list(modules),
        "ruler_sha256": combined,
        "files": entries,
        "product_files": len(product),
        "tool_files": len(entries) - len(product),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = fingerprint()
    text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    print(
        f"{VERSION} ruler={result['ruler_sha256'][:16]} "
        f"product_files={result['product_files']} tool_files={result['tool_files']}"
    )


if __name__ == "__main__":
    main()
