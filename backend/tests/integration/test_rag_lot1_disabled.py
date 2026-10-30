"""DICE (RAG) LOT 1 — preuves du mode DISABLED (mode par défaut).

* un flux complet (upload, analyse, traduction) n'importe aucun module RAG ;
* aucune route ``/api/rag*`` et aucune table ``rag_*`` créée par l'application ;
* ``augment_options`` renvoie l'objet ``options`` reçu, sans lecture en base ;
* l'empreinte de règle (fermeture de mesure gelée) est inchangée.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RULER_REFERENCE = "b0b0261eaabecda8"  # empreinte de référence Phase 0 (d8bb59a)

_SCRIPT = textwrap.dedent(
    """
    import json, sys
    import fitz
    from fastapi.testclient import TestClient
    from sqlalchemy import inspect
    from app.core.models import Tenant, User
    from app.core.security import hash_password
    from app.main import create_app

    app = create_app()
    with app.state.session_factory() as db:
        tenant = Tenant(name="t")
        db.add(tenant)
        db.flush()
        db.add(User(username="u", password_hash=hash_password("Disabled-pass-123"),
                    tenant_id=tenant.id, role="admin"))
        db.commit()
    client = TestClient(app)
    token = client.post("/api/auth/login",
                        json={"username": "u", "password": "Disabled-pass-123"}).json()
    h = {"Authorization": "Bearer " + token["access_token"]}
    pdf = fitz.open(); page = pdf.new_page(width=320, height=220)
    page.insert_text((20, 45), "Gross salary and notice period 1234.", fontsize=12)
    data = pdf.tobytes(); pdf.close()
    doc = client.post("/api/documents", headers=h,
                      files={"file": ("a.pdf", data, "application/pdf")}).json()["id"]
    status = client.post(f"/api/documents/{doc}/translate", headers=h).status_code
    loaded = sorted(m for m in sys.modules
                    if m == "app.rag" or m.startswith("app.rag.")
                    or m == "app.application.rag_bridge")
    print(json.dumps({
        "translate": status,
        "loaded": loaded,
        "paths": sorted(p for p in app.openapi()["paths"] if p.startswith("/api/rag")),
        "tables": sorted(t for t in inspect(app.state.engine).get_table_names()
                         if t.startswith("rag_")),
        "mode": app.state.settings.rag_mode,
    }))
    """
)


def test_disabled_flow_imports_no_rag_module_route_or_table(tmp_path):
    env = {key: value for key, value in os.environ.items() if not key.startswith("TRANSLATOR_RAG_")}
    env.update(
        TRANSLATOR_JWT_SECRET="disabled-secret-0123456789-abcdef",
        TRANSLATOR_DATABASE_URL=f"sqlite:///{tmp_path / 'disabled.db'}",
        TRANSLATOR_DATA_DIR=str(tmp_path / "data"),
        TRANSLATOR_EXECUTION_MODE="inline",
        TRANSLATOR_ENGINE="offline",
        PYTHONPATH=str(ROOT / "backend"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    completed = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr[-2000:]
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    assert result == {
        "translate": 200,
        "loaded": [],
        "paths": [],
        "tables": [],
        "mode": "DISABLED",
    }


def test_augment_options_in_disabled_returns_the_same_object_without_any_access():
    from app.core.settings import Settings
    from app.rag.integration.augment_options import augment_options

    def forbidden(*args, **kwargs):  # pragma: no cover - doit rester inutilisé
        raise AssertionError("aucun accès attendu en DISABLED")

    options = {"glossary": [{"source": "a", "target": "b"}], "memory": {"x": "y"}}
    snapshot = json.dumps(options, sort_keys=True)
    reports = []
    result = augment_options(
        settings=Settings(),
        session_factory=forbidden,
        tenant_id="t",
        document_id="d",
        ir={"pages": []},
        options=options,
        probe=forbidden,
        on_report=reports.append,
        shadow_dispatch=forbidden,
    )
    assert result is options
    assert json.dumps(options, sort_keys=True) == snapshot
    assert reports == []


def test_jobs_hook_is_guarded_and_lazy():
    source = (ROOT / "backend/app/application/jobs.py").read_text(encoding="utf-8")
    header = source.split("\ndef ", 1)[0]
    assert not re.search(r"\brag\b|rag_bridge|app\.rag", header)
    assert 'if getattr(settings, "rag_mode", "DISABLED") != "DISABLED":' in source
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "from .rag" not in main.split("def create_app", 1)[0]


def test_ruler_fingerprint_is_unchanged_and_excludes_rag():
    # fingerprint() charge les modules de mesure dans un sous-processus neuf.
    sys.path.insert(0, str(ROOT / "tools/recette"))
    try:
        import ruler_fingerprint
    finally:
        sys.path.pop(0)
    result = ruler_fingerprint.fingerprint()
    assert result["ruler_sha256"][:16] == RULER_REFERENCE
    assert (result["product_files"], result["tool_files"]) == (29, 5)
    paths = [entry["path"] for entry in result["files"]]
    assert not any("/rag" in path or "rag_bridge" in path for path in paths)
