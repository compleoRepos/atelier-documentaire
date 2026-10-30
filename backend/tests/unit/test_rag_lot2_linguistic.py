"""DICE (RAG) LOT 2 — tests unitaires : linguistique FR/AR/EN/ES/DE, taxonomie, BM25.

Termes fabriqués pour les tests ; aucune donnée réelle.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app.rag.core import lexical, ranking, retrieval
from app.rag.terminology import domains
from app.rag.terminology import linguistic as L


def key(text: str) -> str:
    return L.search_key(text)


def fold(text: str) -> str:
    return L.fold_key(L.search_key(text))


# --- Normalisation de recherche -------------------------------------------------------------


def test_french_elisions_apostrophes_and_case():
    assert key("L'Employeur") == key("l’employeur") == "l' employeur"
    assert key("jusqu'au") == "jusqu' au"
    assert key("aujourd'hui") == "aujourd'hui"  # pas une élision
    assert key("Gross   SALARY") == "gross salary"


def test_latin_diacritics_are_kept_exact_but_folded_except_spanish_enye():
    assert key("Préavis") != key("preavis")
    assert fold("Préavis") == fold("preavis") == "preavis"
    assert fold("cláusula") == "clausula"
    assert fold("año") == "año" and fold("año") != fold("ano")  # ñ distingue des mots


def test_german_eszett_and_umlaut_alias():
    assert key("Straße") == key("strasse")
    assert fold("Kündigung") == "kundigung"
    assert L.alias_keys("Kündigung", "de") == {"kuendigung"}
    assert L.alias_keys("Kündigung", "fr") == set()


def test_arabic_marks_tatweel_alef_digits_and_folding():
    assert key("الرَّاتِب") == key("الـراتب") == key("الراتب")
    assert key("إجازة") == key("اجازة")
    assert key("آجر") == "اجر"
    assert key("٢٠٢٤") == key("۲۰۲۴") == "2024"
    # Pliage (recherche seulement) : taa marbouta et alif maqsoura.
    assert fold("مدرسة") == fold("مدرسه")
    assert fold("على") == fold("علي")
    assert key("مدرسة") != key("مدرسه")  # la clé exacte reste distincte


def test_invisible_and_bidi_controls_are_removed():
    assert key("sal\u200bary") == "salary"
    assert key("\u202bpay\u202c slip") == "pay slip"


def test_bm25_tokens_strip_arabic_clitics_and_elided_articles():
    assert L.bm25_tokens("والراتب") == ["راتب"]
    assert L.bm25_tokens("بالعقد") == ["عقد"]
    assert L.bm25_tokens("l'employeur") == ["employeur"]
    assert L.bm25_tokens("Préavis de départ") == ["preavis", "de", "depart"]


# --- Taxonomie --------------------------------------------------------------------------


def test_taxonomy_has_ten_domains_and_multilingual_aliases():
    assert len(domains.DOMAINS) == 10
    assert {"HR", "LEGAL", "BANKING", "FINANCE", "ADMINISTRATION", "ACADEMIC"} == set(
        domains.CLASSIFIER_DOMAINS
    )
    for alias, code in [
        ("rh", "HR"),
        ("paie", "PAYROLL"),
        ("Nómina", "PAYROLL"),
        ("fiscal", "TAX"),
        ("Versicherung", "INSURANCE"),
        ("banque", "BANKING"),
        ("", "GENERAL"),
    ]:
        assert domains.canonical_domain(alias) == code, alias
    assert domains.canonical_domain("cuisine") is None


@pytest.mark.parametrize(
    ("entry", "document", "expected"),
    [
        ("PAYROLL", "HR", True),
        ("HR", "PAYROLL", True),
        ("NOTARIAL", "LEGAL", True),
        ("TAX", "FINANCE", True),
        ("TAX", "INSURANCE", False),  # domaines frères
        ("HR", "LEGAL", False),
        (None, "HR", True),  # entrée transversale
        ("HR", None, None),  # domaine du document inconnu
        ("HR", "cuisine", None),
        ("cuisine", "HR", False),
    ],
)
def test_domain_compatibility(entry, document, expected):
    assert domains.compatible(entry, document) is expected


# --- BM25 -------------------------------------------------------------------------------


def test_bm25_formula_rare_terms_and_short_documents_score_higher():
    common = lexical._bm25(tf=1, df=50, doc_len=2, n_docs=100, avgdl=2.0)
    rare = lexical._bm25(tf=1, df=1, doc_len=2, n_docs=100, avgdl=2.0)
    long_doc = lexical._bm25(tf=1, df=1, doc_len=8, n_docs=100, avgdl=2.0)
    assert rare > common > 0
    assert rare > long_doc > 0
    expected = math.log(1 + (100 - 1 + 0.5) / 1.5) * 2.2 / (1 + 1.2)
    assert rare == pytest.approx(expected)


def test_entry_tokens_cover_term_synonyms_variants_and_german_alias():
    entry = SimpleNamespace(
        source_term="Kündigung",
        synonyms=["Entlassung", "kündigung"],  # doublon de casse ignoré
        regional_variants=["Kündigungsschreiben"],
        source_language="de",
    )
    counts = lexical.entry_token_counts(entry)
    assert counts == {
        "kundigung": 1,
        "kuendigung": 1,
        "entlassung": 1,
        "kundigungsschreiben": 1,
        "kuendigungsschreiben": 1,
    }
    assert lexical.query_tokens("Kündigung Kündigung  l'Entlassung") == ["kundigung", "entlassung"]


# --- Correspondances : synonymes, variantes, pliage, ambiguïtés ------------------------------


def _entry(i, term, target, *, lang="en", synonyms=None, variants=None, domain=None):
    return SimpleNamespace(
        id=f"e{i:02d}",
        version_id="v1",
        referential_id="r1",
        tenant_id="t",
        source_language=lang,
        source_term=term,
        normalized_source=term.lower(),
        target_language="fr",
        target_term=target,
        synonyms=synonyms,
        regional_variants=variants,
        domain=domain,
        country=None,
        jurisdiction=None,
        register=None,
        definition=None,
        usage_context=None,
    )


SCOPE = [
    {
        "version_id": "v1",
        "content_sha256": "x",
        "number": 1,
        "referential_id": "r1",
        "scope": "tenant",
        "tenant_id": "t",
        "kind": "linguistic",
    }
]


def _rank(entries, text, lang="en", domain="HR", glossary=None):
    index = retrieval.build_index(SCOPE, entries, [])
    details = retrieval.match_details(index, [{"language": lang, "text": text}])
    return ranking.rank(
        index,
        details.term_hits,
        details.notion_hits,
        glossary=ranking.glossary_keys(glossary or []),
        filters=ranking.DocumentFilters(domain=domain),
        max_entries=16,
        details=details,
    ), details


def test_synonym_and_variant_matches_are_reported_with_surface():
    entries = [
        _entry(1, "notice period", "préavis", synonyms=["period of notice"], domain="HR"),
        _entry(
            2, "pay slip", "bulletin de paie", variants=["payslip", "pay stub"], domain="PAYROLL"
        ),
    ]
    selection, details = _rank(entries, "The period of notice is on the PAY STUB.")
    found = {view.id: view for view, _ in selection.terms}
    assert found["e01"].match_kind == "synonym"
    assert found["e02"].match_kind == "variant"  # PAYROLL compatible avec un document HR
    assert details.surfaces["pay stub"] == "PAY STUB"


def test_folded_match_without_ambiguity_is_kept_and_marked():
    entries = [_entry(1, "préavis", "notice period", lang="fr", domain="HR")]
    selection, _ = _rank(entries, "Le preavis est de deux mois.", lang="fr")
    ((view, count),) = selection.terms
    assert view.matched_by == "folded" and count == 1


def test_folded_collision_between_two_entries_is_refused():
    entries = [
        _entry(1, "résumé", "summary", lang="fr"),
        _entry(2, "resume", "resume (CV)", lang="fr"),
    ]
    selection, details = _rank(entries, "Voir le RESUMÉ joint.", lang="fr")
    assert not selection.terms
    assert dict(selection.reasons).get("FOLDED_AMBIGUOUS") == 2
    assert details.folded_ambiguous  # collision signalée
    selection, _ = _rank(entries, "Voir le résumé joint.", lang="fr")
    assert [v.id for v, _ in selection.terms] == ["e01"]  # la forme exacte reste prioritaire


def test_client_glossary_wins_on_folded_keys_too():
    entries = [_entry(1, "préavis", "délai de préavis", lang="fr", domain="HR")]
    selection, _ = _rank(
        entries, "Le preavis court.", lang="fr", glossary=[{"source": "preavis", "target": "x"}]
    )
    assert not selection.terms
    assert dict(selection.reasons).get("GLOSSARY_PRIORITY") == 1


def test_sibling_domain_and_unknown_domain_are_excluded_with_reasons():
    entries = [_entry(1, "premium", "prime d'assurance", domain="INSURANCE")]
    selection, _ = _rank(entries, "The premium is due.", domain="TAX")
    assert not selection.terms and dict(selection.reasons).get("DOMAIN_MISMATCH") == 1
    selection, _ = _rank(entries, "The premium is due.", domain=None)
    assert not selection.terms and dict(selection.reasons).get("DOMAIN_UNKNOWN") == 1


def test_arabic_entry_matches_text_with_harakat_and_clitic_free_key():
    entries = [_entry(1, "الراتب الأساسي", "salaire de base", lang="ar", domain="PAYROLL")]
    selection, _ = _rank(entries, "يبلغ الرَّاتِب الأساسيّ ٣٠٠٠ درهم", lang="ar")
    assert [v.id for v, _ in selection.terms] == ["e01"]


def test_order_is_deterministic_and_entries_deduplicated():
    entries = [
        _entry(2, "gross salary", "salaire brut", synonyms=["gross pay"], domain="HR"),
        _entry(1, "net salary", "salaire net", domain="HR"),
    ]
    text = "Gross pay, gross salary and net salary; gross salary again."
    first, _ = _rank(entries, text)
    second, _ = _rank(list(reversed(entries)), text)
    assert [(v.id, c) for v, c in first.terms] == [(v.id, c) for v, c in second.terms]
    assert len({v.id for v, _ in first.terms}) == len(first.terms)
