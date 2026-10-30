"""DICE (RAG) LOT 2 — terminologie multilingue, BM25, publication et retour arrière (API réelle).

Client HTTP réel, base SQLite de test, flux humain complet (quatre yeux).
Termes fabriqués pour les tests ; aucune donnée réelle.
"""

from __future__ import annotations

import json

from app.application import rag_bridge
from app.rag.models import RagLexicalIndex, RagSearchLog, RagTermPosting

from .rag_support import headers as _login
from .rag_support import make_rag_client, publish_referential


def headers(client, who):
    """Jeton mis en cache par client : la connexion est limitée en fréquence."""
    cache = client.__dict__.setdefault("_rag_tokens", {})
    if who not in cache:
        cache[who] = _login(client, who)
    return cache[who]


ENTRIES = [
    {
        "source_language": "en",
        "source_term": "gross salary",
        "target_language": "fr",
        "target_term": "salaire brut",
        "synonyms": ["gross pay"],
        "domain": "HR",
    },
    {
        "source_language": "en",
        "source_term": "pay slip",
        "target_language": "fr",
        "target_term": "bulletin de paie",
        "regional_variants": ["payslip", "pay stub"],
        "domain": "PAYROLL",
    },
    {
        "source_language": "en",
        "source_term": "notice period",
        "target_language": "fr",
        "target_term": "préavis",
        "domain": "HR",
    },
    {
        "source_language": "ar",
        "source_term": "الراتب الأساسي",
        "target_language": "fr",
        "target_term": "salaire de base",
        "domain": "PAYROLL",
    },
    {
        "source_language": "de",
        "source_term": "Kündigung",
        "target_language": "fr",
        "target_term": "licenciement",
        "synonyms": ["Entlassung"],
        "domain": "HR",
    },
    {
        "source_language": "es",
        "source_term": "nómina",
        "target_language": "fr",
        "target_term": "bulletin de paie",
        "domain": "PAYROLL",
    },
    {
        "source_language": "fr",
        "source_term": "préavis",
        "target_language": "en",
        "target_term": "notice period",
        "domain": "HR",
    },
]


def _setup(monkeypatch, mode="SHADOW", **kwargs):
    client, app, ids = make_rag_client(monkeypatch, mode=mode, **kwargs)
    published = publish_referential(client, ids, entries=ENTRIES, name="RH multilingue")
    return client, app, ids, published


def _search(client, who, text, source, target="fr", domain="HR", path="/api/rag/search"):
    response = client.post(
        path,
        headers=headers(client, who),
        json={
            "text": text,
            "source_language": source,
            "target_language": target,
            "domain": domain,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _publish_new_version(client, referential_id, entries):
    h_author, h_checker = headers(client, "admin-a"), headers(client, "reviewer-a")
    draft = client.post(
        f"/api/rag-admin/referentials/{referential_id}/versions", headers=h_author, json={}
    ).json()
    added = client.post(
        f"/api/rag-admin/versions/{draft['id']}/entries",
        headers=h_author,
        json={"entries": entries},
    )
    assert added.status_code == 200, added.text
    for who, action in ((h_author, "submit"), (h_checker, "validate"), (h_author, "publish")):
        moved = client.post(
            f"/api/rag-admin/versions/{draft['id']}/transitions",
            headers=who,
            json={"action": action},
        )
        assert moved.status_code == 200, (action, moved.text)
    return draft


def _transition(client, version_id, action, who="admin-a"):
    moved = client.post(
        f"/api/rag-admin/versions/{version_id}/transitions",
        headers=headers(client, who),
        json={"action": action},
    )
    assert moved.status_code == 200, (action, moved.text)
    return moved.json()


def test_exact_synonym_variant_and_folded_matches_in_five_languages(app_env, monkeypatch):
    client, _, _, _ = _setup(monkeypatch)
    kinds = {
        r["source_term"]: (r["match_kind"], r["matched_by"])
        for r in _search(client, "admin-a", "Gross pay appears on the PAYSLIP.", "en")["results"]
    }
    assert kinds == {"gross salary": ("synonym", "exact"), "pay slip": ("variant", "exact")}

    arabic = _search(client, "admin-a", "يبلغ الرَّاتِب الأساسيّ ٣٠٠٠ درهم", "ar")["results"]
    assert [r["target_term"] for r in arabic] == ["salaire de base"]

    german = _search(client, "admin-a", "Die Entlassung wurde bestätigt.", "de")["results"]
    assert [(r["target_term"], r["match_kind"]) for r in german] == [("licenciement", "synonym")]

    spanish = _search(client, "admin-a", "Adjunto la nomina de marzo.", "es")["results"]
    assert [(r["target_term"], r["matched_by"]) for r in spanish] == [
        ("bulletin de paie", "folded")
    ]

    french = _search(client, "admin-a", "Le preavis est de deux mois.", "fr", target="en")
    assert [(r["target_term"], r["matched_by"]) for r in french["results"]] == [
        ("notice period", "folded")
    ]


def test_bm25_suggestions_are_explicitly_non_injectable_and_tenant_isolated(app_env, monkeypatch):
    client, app, _, _ = _setup(monkeypatch)
    path = "/api/rag/search/lexical"
    result = _search(client, "admin-a", "monthly salary", "en", path=path)
    assert result["algorithm"] == {
        "name": "BM25",
        "k1": 1.2,
        "b": 0.75,
        "normalizer": "rag-normalizer-2",
    }
    assert result["authority"] == "suggestion_non_injectable"
    assert result["human_review_required"] is True
    assert [r["source_term"] for r in result["results"]] == ["gross salary"]
    assert all(r["injectable"] is False for r in result["results"])
    assert result["indexed_versions"] == 1 and result["unindexed_versions"] == 0

    assert [
        r["source_term"] for r in _search(client, "admin-a", "راتب", "ar", path=path)["results"]
    ] == ["الراتب الأساسي"]
    assert [
        r["source_term"]
        for r in _search(client, "admin-a", "kuendigung", "de", path=path)["results"]
    ] == ["Kündigung"]

    other = _search(client, "admin-b", "monthly salary", "en", path=path)
    assert other["results"] == [] and other["indexed_versions"] == 0

    with app.state.session_factory() as db:
        logs = db.query(RagSearchLog).filter(RagSearchLog.mode == "LEXICAL").all()
        owners = {p.tenant_id for p in db.query(RagTermPosting).all()}
    assert len(logs) == 4 and len(owners) == 1  # postings du seul tenant A
    dumped = json.dumps([[r.filters, r.outcome, r.result_ids] for r in logs], ensure_ascii=False)
    for word in ("salary", "راتب", "kuendigung"):
        assert word not in dumped


def test_bm25_suggestion_is_never_injected_into_translation(app_env, monkeypatch):
    from app.ai.translation.service import EngineResult, TranslationEngine

    class Engine(TranslationEngine):
        tokenizer_name = "test-double-words"

        async def translate_chunk(self, messages, expected_ids, *, max_output):
            return EngineResult(translations={i: "x" for i in expected_ids})

    client, app, ids = make_rag_client(monkeypatch, mode="ASSISTED")
    publish_referential(client, ids, entries=ENTRIES, name="RH", max_mode="ASSISTED")
    ir = {
        "language": "en",
        "domain": "HR",
        "pages": [{"number": 1, "blocks": [{"id": "b1", "text": "The salary is paid monthly."}]}],
    }
    lexical = _search(
        client, "admin-a", "The salary is paid monthly.", "en", path="/api/rag/search/lexical"
    )
    assert [r["source_term"] for r in lexical["results"]] == ["gross salary"]  # suggestion seule
    options = {
        "engine": "private",
        "translation_engine": Engine(),
        "target_language": "fr",
        "glossary": [],
        "memory": {},
    }
    reports = []
    result = rag_bridge.augment_translation_options(
        app.state.settings,
        app.state.session_factory,
        ids["tenant-a"],
        None,
        ir,
        options,
        on_report=reports.append,
    )
    terminology = (result.get("document_memory") or {}).get("terminology") or []
    assert all(item["source"] != "gross salary" for item in terminology)
    assert reports[0].get("injected_term_ids", []) == []


def test_publication_rollback_diff_history_and_index_follow_the_published_version(
    app_env, monkeypatch
):
    client, app, _, published = _setup(monkeypatch)
    referential_id = published["referential"]["id"]
    v1 = published["version"]["id"]
    with app.state.session_factory() as db:
        v1_postings = db.query(RagTermPosting).filter_by(version_id=v1).count()
        v1_built = db.get(RagLexicalIndex, v1).built_at
    assert v1_postings > 0

    changed = [dict(e) for e in ENTRIES if e["source_term"] != "nómina"]
    for entry in changed:
        if entry["source_term"] == "notice period":
            entry["target_term"] = "délai de préavis"
    changed.append(
        {
            "source_language": "en",
            "source_term": "net salary",
            "target_language": "fr",
            "target_term": "salaire net",
            "domain": "PAYROLL",
        }
    )
    v2 = _publish_new_version(client, referential_id, changed)["id"]

    exact = _search(client, "admin-a", "The notice period applies.", "en")["results"]
    assert [r["target_term"] for r in exact] == ["délai de préavis"]
    lexical = _search(client, "admin-a", "notice", "en", path="/api/rag/search/lexical")
    assert [r["target_term"] for r in lexical["results"]] == ["délai de préavis"]

    h = headers(client, "admin-a")
    diff = client.get(f"/api/rag-admin/versions/{v2}/diff", params={"against": v1}, headers=h)
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert body["counts"] == {"added": 1, "removed": 1, "changed": 1, "unchanged": 5}
    assert body["changed"][0]["fields"] == ["target_term"]
    assert body["changed"][0]["before"]["target_term"] == "préavis"
    assert [e["source_term"] for e in body["added"]] == ["net salary"]
    assert [e["source_term"] for e in body["removed"]] == ["nómina"]

    history = client.get(f"/api/rag-admin/referentials/{referential_id}/history", headers=h).json()
    assert [(v["number"], v["status"]) for v in history["versions"]] == [
        (1, "retired"),
        (2, "published"),
    ]
    actions = [e["action"] for e in history["events"]]
    assert actions.count("publish") == 2 and "retire" in actions and "validate" in actions

    # Retour arrière humain : la v1 redevient la seule version publiée.
    _transition(client, v1, "restore")
    exact = _search(client, "admin-a", "The notice period applies.", "en")["results"]
    assert [r["target_term"] for r in exact] == ["préavis"]
    lexical = _search(client, "admin-a", "notice", "en", path="/api/rag/search/lexical")
    assert [r["target_term"] for r in lexical["results"]] == ["préavis"]
    assert lexical["indexed_versions"] == 1
    with app.state.session_factory() as db:
        assert db.query(RagTermPosting).filter_by(version_id=v1).count() == v1_postings
        assert db.get(RagLexicalIndex, v1).built_at == v1_built  # index réutilisé (idempotent)
    history = client.get(f"/api/rag-admin/referentials/{referential_id}/history", headers=h).json()
    assert [(v["number"], v["status"]) for v in history["versions"]] == [
        (1, "published"),
        (2, "retired"),
    ]

    # Retrait sans remplaçant : plus aucune suggestion ni correspondance.
    _transition(client, v1, "retire")
    assert (
        _search(client, "admin-a", "notice", "en", path="/api/rag/search/lexical")["results"] == []
    )
    assert _search(client, "admin-a", "The notice period applies.", "en")["results"] == []


def test_missing_index_is_reported_then_rebuilt_by_rag_admin_only(app_env, monkeypatch):
    client, app, _, published = _setup(monkeypatch)
    version_id = published["version"]["id"]
    with app.state.session_factory() as db:
        db.query(RagTermPosting).filter_by(version_id=version_id).delete()
        db.query(RagLexicalIndex).filter_by(version_id=version_id).delete()
        db.commit()
    path = "/api/rag/search/lexical"
    result = _search(client, "admin-a", "salary", "en", path=path)
    assert result["results"] == [] and result["unindexed_versions"] == 1
    status = client.get("/api/rag-admin/lexical/status", headers=headers(client, "admin-a")).json()
    assert [v["indexed"] for v in status["versions"]] == [False]

    denied = client.post("/api/rag-admin/lexical/rebuild", headers=headers(client, "reviewer-a"))
    assert denied.status_code == 403
    rebuilt = client.post("/api/rag-admin/lexical/rebuild", headers=headers(client, "admin-a"))
    assert rebuilt.status_code == 200 and rebuilt.json() == {"built": 1, "reused": 0}
    again = client.post("/api/rag-admin/lexical/rebuild", headers=headers(client, "admin-a"))
    assert again.json() == {"built": 0, "reused": 1}
    assert [
        r["source_term"] for r in _search(client, "admin-a", "salary", "en", path=path)["results"]
    ] == ["gross salary"]

    # Le tenant B ne voit ni l'état d'index ni l'historique du tenant A.
    other = client.get("/api/rag-admin/lexical/status", headers=headers(client, "admin-b"))
    assert other.status_code in (200, 403)
    if other.status_code == 200:
        assert other.json()["versions"] == []
    # Une reconstruction demandée par le tenant B ne touche aucune version du tenant A.
    other_rebuild = client.post(
        "/api/rag-admin/lexical/rebuild", headers=headers(client, "admin-b")
    )
    assert other_rebuild.status_code in (200, 403)
    if other_rebuild.status_code == 200:
        assert other_rebuild.json() == {"built": 0, "reused": 0}
    with app.state.session_factory() as db:
        assert db.query(RagLexicalIndex).filter_by(version_id=version_id).count() == 1
    referential_id = published["referential"]["id"]
    hidden = client.get(
        f"/api/rag-admin/referentials/{referential_id}/history", headers=headers(client, "admin-b")
    )
    assert hidden.status_code in (403, 404)
