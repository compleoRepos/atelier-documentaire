from app.ai.quality.entities import compare_entities, extract_entities


def test_extractor_covers_explicit_types_and_reports_regex_limit():
    text = "Nom: Mohamed Alaoui; email: a.ou@example.com; date: 12/03/2024; total: EUR 1,250.00"
    entities = extract_entities(text)
    kinds = {item["type"] for item in entities}
    assert {"name", "email", "date", "amount"} <= kinds
    assert any(item["source"] == "regex" for item in entities)


def test_date_changed_is_critical_not_a_lexical_translation_failure():
    result = compare_entities("Date: 12/03/2024", "Date: 12/03/2025")
    assert any(issue["code"] == "CRITICAL_ENTITY_MODIFIED" for issue in result["errors"])


def test_name_changed_is_critical_with_annotation():
    annotation = [{"type": "name", "value": "Mohamed Alaoui"}]
    result = compare_entities(
        "Beneficiary: Mohamed Alaoui", "Bénéficiaire: Ahmed Alaoui", annotation
    )
    assert any(issue["code"] == "CRITICAL_ENTITY_MODIFIED" for issue in result["errors"])


def test_two_occurrences_are_compared_independently():
    result = compare_entities("Date 12/03/2024 puis 12/03/2024", "Date 12/03/2024")
    missing = [issue for issue in result["errors"] if issue["code"] == "CRITICAL_ENTITY_MISSING"]
    assert missing and missing[0]["occurrence"] == 2


def test_sign_loss_is_not_an_invariant_match():
    result = compare_entities("Solde: -1234", "Solde: 1234")
    assert any(issue["code"] == "CRITICAL_ENTITY_MODIFIED" for issue in result["errors"])


def test_same_invariants_with_translated_labels_do_not_raise():
    result = compare_entities(
        "Date: 12/03/2024; Total: EUR 10", "Date : 12/03/2024 ; Total : EUR 10"
    )
    assert result["errors"] == []
