#!/usr/bin/env python3
"""Matrice de charge de laboratoire: (clients,pages) sans extrapolation industrielle."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CASES = [(1, 1), (1, 10), (1, 50), (1, 100), (1, 200), (10, 1), (50, 1), (100, 1)]


def main() -> int:
    p = argparse.ArgumentParser(description="Matrice bornée synthétique native française")
    p.add_argument("--base-url", default=os.getenv("LOAD_TEST_BASE_URL", "http://127.0.0.1:8080"))
    p.add_argument(
        "--credentials-file", type=Path, default=Path("/tmp/translator-lab-credentials.json")
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument(
        "--execute", action="store_true", help="exécuter les cas; sinon produire un plan NOT_TESTED"
    )
    args = p.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, (users, pages) in enumerate(CASES, 1):
        print(f"cas {i}/8 clients={users} pages={pages}", flush=True)
        row = {
            "case": i,
            "virtual_clients": users,
            "pages_per_document": pages,
            "identity_mode": "1 identité réutilisée par client virtuel (outil existant)"
            if users == 1
            else "1 compte de laboratoire partagé entre clients virtuels; pas 100 identités",
            "synthetic_only": True,
            "native_pdf": True,
            "ocr_seconds": None,
            "llm_seconds": None,
            "gpu_seconds": None,
            "queue_workers_cpu": None,
            "queue_workers_memory": None,
        }
        if not args.execute:
            row.update(status="NOT_TESTED", reason="plan généré sans exécution")
        else:
            out = args.output.parent / f"load-case-{i}.json"
            env = os.environ.copy()
            env.update(
                LOAD_TEST_USERNAME=json.loads(args.credentials_file.read_text())["username"],
                LOAD_TEST_PASSWORD=json.loads(args.credentials_file.read_text())["password"],
            )
            cmd = [
                sys.executable,
                "tools/load_test.py",
                "--base-url",
                args.base_url,
                "--users",
                str(users),
                "--pages",
                str(pages),
                "--timeout",
                str(args.timeout),
                "--output",
                str(out),
            ]
            t = time.perf_counter()
            proc = subprocess.run(
                cmd, env=env, capture_output=True, text=True, timeout=args.timeout + 30
            )
            row.update(
                status="PASS" if proc.returncode == 0 else "FAIL",
                elapsed_seconds=round(time.perf_counter() - t, 3),
                result_file=str(out),
                stderr_tail=proc.stderr[-500:],
            )
            if out.exists():
                data = json.loads(out.read_text())
                row.update(
                    {
                        k: data.get(k)
                        for k in (
                            "total_seconds",
                            "average_seconds",
                            "p95_seconds",
                            "throughput_documents_per_second",
                            "successes",
                            "errors",
                        )
                    }
                )
        rows.append(row)
    result = {
        "method": "load_test.py existant, PDF natif français synthétique, transport HTTP privé",
        "scope": "offline/native; axes indépendants, pas de cartésien 100x200; pas de SLO inventé",
        "cases": rows,
        "status": "NOT_TESTED"
        if not args.execute
        else ("PASS" if all(x["status"] == "PASS" for x in rows) else "FAIL"),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "cases": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
