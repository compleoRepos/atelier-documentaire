"""DICE (RAG) LOT 1 — API, rôles, validation humaine et isolation des tenants."""

from __future__ import annotations

import json

from .rag_support import TERMS_EN_FR, grant, headers, make_rag_client, publish_referential


def test_admin_router_is_hidden_unless_enabled(app_env, monkeypatch):
    client, app, _ = make_rag_client(monkeypatch, mode="SHADOW", admin=False)
    paths = set(app.openapi()["paths"])
    assert "/api/rag/status" in paths
    assert not any(path.startswith("/api/rag-admin") for path in paths)
    assert (
        client.get("/api/rag-admin/referentials", headers=headers(client, "admin-a")).status_code
        == 404
    )


def test_status_reports_effective_mode_and_tenant_cannot_exceed_global(app_env, monkeypatch):
    client, _, ids = make_rag_client(monkeypatch, mode="SHADOW")
    h = headers(client, "admin-a")
    status = client.get("/api/rag/status", headers=h).json()
    assert status["global_mode"] == "SHADOW"
    assert status["tenant_max_mode"] == "DISABLED"
    assert status["effective_mode"] == "DISABLED"
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    refused = client.post("/api/rag-admin/tenant", headers=h, json={"max_mode": "ASSISTED"})
    assert refused.status_code == 409
    accepted = client.post("/api/rag-admin/tenant", headers=h, json={"max_mode": "SHADOW"})
    assert accepted.status_code == 200
    assert client.get("/api/rag/status", headers=h).json()["effective_mode"] == "SHADOW"
    # L'autre tenant reste DISABLED : le réglage est isolé.
    other = client.get("/api/rag/status", headers=headers(client, "user-b")).json()
    assert other["effective_mode"] == "DISABLED"


def test_four_eyes_validation_and_no_automatic_publication(app_env, monkeypatch):
    client, _, ids = make_rag_client(monkeypatch, mode="SHADOW")
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    grant(client, "admin-a", ids["admin-a"], "terminology_manager")
    grant(client, "admin-a", ids["reviewer-a"], "terminology_manager")
    h_admin, h_rev = headers(client, "admin-a"), headers(client, "reviewer-a")
    ref = client.post(
        "/api/rag-admin/referentials", headers=h_admin, json={"kind": "linguistic", "name": "RH"}
    ).json()
    version = client.post(
        f"/api/rag-admin/referentials/{ref['id']}/versions", headers=h_admin, json={}
    ).json()
    client.post(
        f"/api/rag-admin/versions/{version['id']}/entries",
        headers=h_admin,
        json={"entries": TERMS_EN_FR},
    )
    url = f"/api/rag-admin/versions/{version['id']}/transitions"
    # Pas de publication sans validation, pas d'auto-validation.
    assert client.post(url, headers=h_admin, json={"action": "publish"}).status_code == 409
    assert client.post(url, headers=h_admin, json={"action": "submit"}).status_code == 200
    assert client.post(url, headers=h_admin, json={"action": "validate"}).status_code == 403
    search = {"text": "gross salary", "source_language": "en", "domain": "hr"}
    assert client.post("/api/rag/search", headers=h_admin, json=search).json()["results"] == []
    assert client.post(url, headers=h_rev, json={"action": "validate"}).status_code == 200
    assert client.post("/api/rag/search", headers=h_admin, json=search).json()["results"] == []
    assert client.post(url, headers=h_admin, json={"action": "publish"}).status_code == 200
    # Publié mais référentiel inactif : toujours rien.
    assert client.post("/api/rag/search", headers=h_admin, json=search).json()["results"] == []
    client.post(
        f"/api/rag-admin/referentials/{ref['id']}/active", headers=h_admin, json={"active": True}
    )
    results = client.post("/api/rag/search", headers=h_admin, json=search).json()["results"]
    assert [item["target_term"] for item in results] == ["salaire brut"]
    events = client.get(f"/api/rag-admin/versions/{version['id']}/events", headers=h_admin).json()
    assert [event["action"] for event in events] == [
        "create",
        "edit",
        "submit",
        "validate",
        "publish",
    ]
    assert len({event["actor_id"] for event in events if event["action"] != "create"}) == 2


def test_tenant_isolation_for_referentials_search_logs_and_documents(app_env, monkeypatch):
    client, _, ids = make_rag_client(monkeypatch, mode="SHADOW")
    published = publish_referential(client, ids, tenant="a")
    version_id = published["version"]["id"]
    grant(client, "admin-b", ids["admin-b"], "rag_admin")
    h_b = headers(client, "admin-b")
    assert client.get("/api/rag-admin/referentials", headers=h_b).json() == []
    assert (
        client.get(f"/api/rag-admin/versions/{version_id}/entries", headers=h_b).status_code == 404
    )
    assert (
        client.post(
            f"/api/rag-admin/versions/{version_id}/transitions",
            headers=h_b,
            json={"action": "retire"},
        ).status_code
        == 404
    )
    search = {"text": "gross salary and notice period", "source_language": "en", "domain": "hr"}
    assert client.post("/api/rag/search", headers=h_b, json=search).json()["results"] == []
    h_a = headers(client, "admin-a")
    assert len(client.post("/api/rag/search", headers=h_a, json=search).json()["results"]) == 2
    log_a = client.get("/api/rag-admin/search-log", headers=h_a).json()
    log_b = client.get("/api/rag-admin/search-log", headers=h_b).json()
    assert len(log_a) == 1 and len(log_b) == 1
    assert log_a[0]["result_count"] == 2 and log_b[0]["result_count"] == 0
    assert {row["id"] for row in log_a}.isdisjoint({row["id"] for row in log_b})
    from app.rag.models import RagSearchLog

    with client.app.state.session_factory() as db:
        owners = {row.id: row.tenant_id for row in db.query(RagSearchLog).all()}
    assert owners[log_a[0]["id"]] == ids["tenant-a"]
    assert owners[log_b[0]["id"]] == ids["tenant-b"]
    # Le journal ne contient jamais le texte recherché, seulement son empreinte.
    dumped = json.dumps(log_a + log_b, ensure_ascii=False)
    assert "gross salary" not in dumped and "notice period" not in dumped
    assert all(len(row["query_sha256"]) == 64 for row in log_a)


def test_document_context_requires_tenant_and_four_eyes(app_env, monkeypatch):
    from .test_rag_lot1_shadow import upload_pdf

    client, _, ids = make_rag_client(monkeypatch, mode="SHADOW")
    doc_id = upload_pdf(client, "admin-a", "Gross salary and notice period 1234.")
    h_admin, h_rev, h_b = (
        headers(client, "admin-a"),
        headers(client, "reviewer-a"),
        headers(client, "admin-b"),
    )
    url = f"/api/rag/documents/{doc_id}/context"
    declared = client.post(
        url, headers=h_admin, json={"source_country": "FR", "jurisdiction": "FR"}
    )
    assert declared.status_code == 200, declared.text
    assert declared.json()["status"] == "declared"
    assert client.get(url, headers=h_b).status_code == 404
    assert client.post(url, headers=h_b, json={"source_country": "MA"}).status_code == 404
    assert client.post(f"{url}/validate", headers=h_admin).status_code == 403
    validated = client.post(f"{url}/validate", headers=h_rev)
    assert validated.status_code == 200, validated.text
    assert validated.json()["status"] == "validated"
    # Toute modification repasse en « declared » et exige une nouvelle validation.
    again = client.post(url, headers=h_rev, json={"source_country": "MA"})
    assert again.json()["status"] == "declared"
    assert client.get(f"/api/rag/documents/{doc_id}/explanation", headers=h_b).status_code == 404
    explanation = client.get(f"/api/rag/documents/{doc_id}/explanation", headers=h_admin)
    assert explanation.status_code == 200
    assert explanation.json()["human_review_required"] is True


def test_common_library_is_read_only_for_tenants(app_env, monkeypatch):
    from app.rag.models import RagReferential, RagReferentialVersion, RagTermEntry

    client, app, ids = make_rag_client(monkeypatch, mode="SHADOW")
    factory = app.state.session_factory
    with factory() as db:  # outillage plateforme : seule voie d'écriture du commun
        ref = RagReferential(
            tenant_id=None, scope="common", kind="linguistic", name="Commun", active=True
        )
        db.add(ref)
        db.flush()
        version = RagReferentialVersion(
            tenant_id=None,
            referential_id=ref.id,
            number=1,
            status="published",
            content_sha256="0" * 64,
            entry_count=1,
        )
        db.add(version)
        db.flush()
        db.add(
            RagTermEntry(
                tenant_id=None,
                referential_id=ref.id,
                version_id=version.id,
                source_language="en",
                source_term="pay slip",
                normalized_source="pay slip",
                target_language="fr",
                target_term="bulletin de paie",
                status="validated",
            )
        )
        db.commit()
        ref_id, version_id = ref.id, version.id
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    grant(client, "admin-a", ids["admin-a"], "terminology_manager")
    h = headers(client, "admin-a")
    listed = client.get("/api/rag-admin/referentials", headers=h).json()
    assert [(item["id"], item["scope"]) for item in listed] == [(ref_id, "common")]
    for method, url, body in (
        ("post", f"/api/rag-admin/referentials/{ref_id}/versions", {}),
        ("post", f"/api/rag-admin/referentials/{ref_id}/active", {"active": False}),
        ("post", f"/api/rag-admin/versions/{version_id}/transitions", {"action": "retire"}),
        ("post", f"/api/rag-admin/versions/{version_id}/entries", {"entries": TERMS_EN_FR[:1]}),
    ):
        response = getattr(client, method)(url, headers=h, json=body)
        assert response.status_code == 403, (url, response.text)
    search = {"text": "pay slip", "source_language": "en"}
    for user in ("admin-a", "admin-b"):
        found = client.post("/api/rag/search", headers=headers(client, user), json=search).json()
        assert [item["target_term"] for item in found["results"]] == ["bulletin de paie"]


def test_roles_are_required_and_isolated(app_env, monkeypatch):
    client, _, ids = make_rag_client(monkeypatch, mode="SHADOW")
    h_up = headers(client, "uploader-a")
    assert client.get("/api/rag-admin/referentials", headers=h_up).status_code == 403
    assert (
        client.post(
            "/api/rag/search", headers=h_up, json={"text": "x", "source_language": "en"}
        ).status_code
        == 403
    )
    # Un administrateur ne peut pas donner un rôle à un utilisateur d'un autre tenant.
    cross = client.post(
        "/api/rag-admin/roles",
        headers=headers(client, "admin-a"),
        json={"user_id": ids["user-b"], "role": "reader"},
    )
    assert cross.status_code == 404
    grant(client, "admin-a", ids["uploader-a"], "reader")
    assert client.get("/api/rag-admin/referentials", headers=h_up).status_code == 200
    created = client.post(
        "/api/rag-admin/referentials", headers=h_up, json={"kind": "linguistic", "name": "x"}
    )
    assert created.status_code == 403


def test_regulatory_publication_is_reserved_to_legal_manager(app_env, monkeypatch):
    client, _, ids = make_rag_client(monkeypatch, mode="SHADOW")
    for user in ("admin-a", "reviewer-a"):
        grant(client, "admin-a", ids[user], "rag_admin")
        grant(client, "admin-a", ids[user], "terminology_manager")
    h_admin = headers(client, "admin-a")
    created = client.post(
        "/api/rag-admin/referentials",
        headers=h_admin,
        json={"kind": "regulatory", "name": "Textes FR", "country": "FR"},
    )
    assert created.status_code == 403
    grant(client, "admin-a", ids["admin-a"], "legal_manager")
    grant(client, "admin-a", ids["reviewer-a"], "legal_manager")
    created = client.post(
        "/api/rag-admin/referentials",
        headers=h_admin,
        json={"kind": "regulatory", "name": "Textes FR", "country": "FR"},
    )
    assert created.status_code == 200, created.text
