"""F-L2-03 : un terme collé à une ponctuation était écarté du contexte (constructeur GELÉ).

Branche dédiée ``fix/f-l2-03-ponctuation-contexte-20261030`` : le correctif ajoute aux
jetons du bloc leur forme sans ponctuation de bord (union). Ces tests vérifient :

* le cas d'origine (``Bruttogehalt:``) et les ponctuations des langues concernées ;
* la monotonie : tout élément retenu par le comportement historique l'est encore ;
* l'absence d'effet sur les règles de domaine et de longueur minimale des jetons.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.ai.context.builder import ContextPackBuilder

GLOSSARY = {"glossary": [{"source": "Bruttogehalt", "target": "rémunération brute"}]}


def _terms_sent(
    text: str, options: dict[str, Any] = GLOSSARY, ir: dict[str, Any] | None = None
) -> list:
    builder = ContextPackBuilder(tokenizer=None, max_tokens=10**9)
    chunk = {"blocks": [{"id": "b001", "text": text}]}
    # La clé « terms » est omise quand aucun terme n'est retenu (comportement historique).
    return builder.relevant_context(ir or {"pages": []}, chunk, options).get("terms", [])


def _historical_relevant(text: str, entries: list[dict[str, str]]) -> list[dict[str, str]]:
    """Copie du critère historique (découpage sur espaces seulement), pour la monotonie."""
    terms = set(text.lower().split())
    out = []
    for item in entries:
        hay = " ".join(str(item.get(k, "")) for k in ("source", "target", "domain")).lower()
        if not hay or any(term in hay for term in terms if len(term) > 2):
            out.append(item)
    return out[:12]


def test_glossary_entry_is_sent_when_the_word_stands_alone():
    assert _terms_sent("Bruttogehalt 3.831,25 EUR") == GLOSSARY["glossary"]


def test_glossary_entry_is_sent_when_followed_by_punctuation():
    assert _terms_sent("Bruttogehalt: 3.831,25 EUR") == GLOSSARY["glossary"]


@pytest.mark.parametrize(
    ("text", "source"),
    [
        ("Bruttogehalt: 3.831,25 EUR", "Bruttogehalt"),
        ("(Nettogehalt)", "Nettogehalt"),
        ("«salaire», versé mensuellement", "salaire"),
        ("¿Indemnización?", "Indemnización"),
        ("الراتب، الشهري", "الراتب"),
        ("الراتب؛", "الراتب"),
    ],
)
def test_punctuation_of_concerned_languages(text: str, source: str) -> None:
    entry = {"source": source, "target": "terme validé"}
    assert _terms_sent(text, {"glossary": [entry]}) == [entry]


def test_scripts_without_spaces_remain_a_known_limit() -> None:
    # « 工资：2450 » reste un seul jeton après retrait des bords : hors périmètre F-L2-03
    # (segmentation des écritures sans espace, traitée par la recherche DICE).
    entry = {"source": "工资", "target": "salaire"}
    assert _terms_sent("工资：2450", {"glossary": [entry]}) == []


@pytest.mark.parametrize(
    "text",
    [
        "Bruttogehalt 3.831,25 EUR",
        "Salaire brut : 2450 EUR (mensuel)",
        "Le salarié perçoit une prime, versée en mars.",
        "Total: 1.910,00 — Net",
        "",
    ],
)
def test_monotonic_with_historical_behaviour(text: str) -> None:
    entries = [
        {"source": "Bruttogehalt", "target": "rémunération brute"},
        {"source": "salaire brut", "target": "salaire brut"},
        {"source": "prime", "target": "prime"},
        {"source": "net", "target": "net"},
        {"source": "Lohnsteuer", "target": "impôt sur le salaire"},
    ]
    historical = _historical_relevant(text, entries)
    current = _terms_sent(text, {"glossary": entries})
    assert all(item in current for item in historical)


def test_short_tokens_still_ignored_after_stripping() -> None:
    assert _terms_sent("(EU)", {"glossary": [{"source": "Bruttogehalt", "target": "x"}]}) == []


def test_domain_rule_unchanged() -> None:
    entry = {"source": "Bruttogehalt", "target": "rémunération brute", "domain": "banking"}
    assert (
        _terms_sent("Bruttogehalt:", {"glossary": [entry]}, {"pages": [], "domain": "payroll"})
        == []
    )
    assert _terms_sent(
        "Bruttogehalt:", {"glossary": [entry]}, {"pages": [], "domain": "banking"}
    ) == [entry]
