"""RUN27 F29 regressions (synthetic, invented texts only)."""

from app.ai.quality import engine
from app.ai.quality.entities import compare_entities, extract_entities
from app.ai.translation import service
from app.documents import ocr_recovery


def _block(text, language="spa", confidence=0.8):
    return {
        "text": text,
        "language": language,
        "confidence": confidence,
        "source_lines": [{"text": text}],
    }


# --- A: numbers glued to a following letter, symmetric integrity check -------


def test_a_glued_amount_and_ordinal_are_protected_by_markers():
    protected, mapping, _ = service._protected_text(
        "Totale 41.207.30euro dal 3rd giorno, art 27bis", [], "b1"
    )
    assert {"41.207.30", "3", "27"} <= set(mapping.values())
    assert "41.207.30" not in protected and "⟦BTP-P" in protected


def test_a_correct_ordinal_translation_is_no_longer_rejected():
    restored, issue = service._restore_and_validate(
        "The season runs from 2nd March to 30th November",
        "La saison va du 2 mars au 30 novembre",
        {},
        "b1",
    )
    assert issue is None and restored.endswith("30 novembre")


def test_a_modified_identifier_with_glued_digits_is_now_detected():
    _, issue = service._restore_and_validate("Ref XQ4471 attached", "Réf. XQ4472 jointe", {}, "b1")
    assert issue and issue["code"] == "PROTECTED_ENTITY_CHANGED"


def test_a_digit_invented_by_the_model_is_detected():
    # OCR read a letter ("Bl"), the model "corrects" it into a digit ("B1").
    _, issue = service._restore_and_validate(
        "Bat Bl B2 rue des Lilas", "Bâtiment B1 B2 rue des Lilas", {}, "b1"
    )
    assert issue and issue["code"] == "PROTECTED_ENTITY_CHANGED"


def test_a_amount_reformatted_by_the_model_is_still_rejected():
    _, issue = service._restore_and_validate("montant 41.207.30", "montant 41 207,30", {}, "b1")
    assert issue and issue["code"] == "PROTECTED_ENTITY_CHANGED"


# --- B: lexical plausibility of a confident OCR reading ----------------------

DEFORMED = (
    "La emprexa se compronete a rcalizar los trabjos fiyos disconfinuos segtn ol artieulo tercoro"
)
READABLE = (
    "La empresa se compromete a realizar los trabajos fijos discontinuos segun el articulo tercero"
)


def test_b_deformed_latin_reading_goes_to_review_and_readable_one_does_not():
    assert ocr_recovery.known_share(DEFORMED, "spa", ["spa"]) < ocr_recovery.IMPLAUSIBLE_BELOW
    assert ocr_recovery.lexically_implausible(_block(DEFORMED), ["spa"]) is True
    assert ocr_recovery.lexically_implausible(_block(READABLE), ["spa"]) is False


def test_b_gate_does_not_apply_outside_its_evidence():
    short = "La emprexa se compronete a rcalizar"
    assert ocr_recovery.lexically_implausible(_block(short), ["spa"]) is False  # < 8 words
    assert (
        ocr_recovery.lexically_implausible(_block(DEFORMED, language="unknown"), ["spa"]) is False
    )
    arabic = (
        "تلتزم الشركة بتنفيذ الأعمال الثابتة المتقطعة وفق المادة الثالثة من النظام الأساسي للعمال"
    )
    assert ocr_recovery.lexically_implausible(_block(arabic, language="ara"), ["ara"]) is False
    no_conf = {"text": DEFORMED, "language": "spa", "confidence": None, "source_lines": [{}]}
    assert ocr_recovery.lexically_implausible(no_conf, ["spa"]) is False


def test_b_line_verification_wires_the_gate():
    from app.documents import line_verification

    assert line_verification.VERSION == "line-verification-11"
    assert line_verification.lexically_implausible is ocr_recovery.lexically_implausible


# --- C: units in their accented French and corpus-language forms -------------


def test_c_accented_french_metre_is_the_same_unit():
    src = "the fence is 12 metres long and the gate is 1 metre wide"
    tgt = "la clôture mesure 12 mètres et le portail 1 mètre de large"
    assert engine._unit_occurrences(src) == engine._unit_occurrences(tgt) == ["m", "m"]
    _, hallucinations, _ = engine._entity_and_hallucination_checks(src, tgt, {}, None)
    assert not [h for h in hallucinations if h["code"] == "HALLUCINATION_UNIT_CHANGED"]


def test_c_source_language_forms_are_symmetric():
    for src in ("lungo 12 metri", "mide 12 metros", "lang 12 meter"):
        assert (
            engine._unit_occurrences(src) == engine._unit_occurrences("mesure 12 mètres") == ["m"]
        )
    assert engine._unit_occurrences("5 litri") == engine._unit_occurrences("5 litres") == ["l"]


def test_c_a_really_lost_unit_is_still_reported():
    _, hallucinations, _ = engine._entity_and_hallucination_checks(
        "a fence of 12 metres", "une clôture de 12", {}, None
    )
    assert [h for h in hallucinations if h["code"] == "HALLUCINATION_UNIT_CHANGED"]


# --- D: month glued to the year by the OCR -----------------------------------


def test_d_glued_month_year_is_a_date_not_an_immutable_code():
    entities = extract_entities("14 October2023")
    assert [e["type"] for e in entities] == ["date"]
    assert compare_entities("14 October2023", "14 Octobre2023", [])["errors"] == []


def test_d_a_changed_glued_date_is_still_reported():
    errors = compare_entities("14 October2023", "15 Octobre2023", [])["errors"]
    assert errors and errors[0]["code"] == "CRITICAL_ENTITY_MODIFIED"


# --- E: translation-memory hits are re-checked by the CURRENT guard ------------


def _launcher():
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "interim_owner_corpus_run_run27", root / "tools" / "interim_owner_corpus_run.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_e_hit_refused_by_the_previous_guard_is_sent_again():
    launcher = _launcher()
    block = {"id": "b1", "text": "From 2nd March to 30th November"}
    codes = launcher._issue_codes_by_block(
        [{"code": "PROTECTED_ENTITY_CHANGED", "block_id": "b1"}, {"code": "X", "block_ids": ["b2"]}]
    )
    assert codes == {"b1": {"PROTECTED_ENTITY_CHANGED"}, "b2": {"X"}}
    reason = launcher._hit_invalidation(block, block["text"], codes["b1"])
    assert reason == "previous_guard_rejection"


def test_e_cached_target_with_an_invented_digit_is_not_reused():
    launcher = _launcher()
    block = {"id": "b1", "text": "Lot Kl K7 rue du Port"}
    reason = launcher._hit_invalidation(block, "Lot K1 K7 rue du Port", set())
    assert reason == "current_guard_rejects_cached_target"


def test_e_valid_or_untouched_hits_are_still_reused():
    launcher = _launcher()
    block = {"id": "b1", "text": "Factura 4410 del 12/03"}
    assert launcher._hit_invalidation(block, "Facture 4410 du 12/03", set()) is None
    assert launcher._hit_invalidation(block, block["text"], {"UNTRANSLATED"}) is None


# --- F34: a French ordinal suffix on a number other than 1 is refused ----------


def test_f34_invalid_french_ordinal_is_refused_and_source_kept():
    from app.ai.translation import service

    source = "Leave runs from 2nd May to 21st June"
    text, issue = service._restore_and_validate(
        source, "Le congé court du 2er mai au 21er juin", {}, "b1", "fr"
    )
    assert text == source
    assert issue["code"] == "IMPLAUSIBLE_TARGET_ORDINAL"
    assert issue["block_id"] == "b1"


def test_f34_valid_french_ordinals_and_other_targets_are_accepted():
    from app.ai.translation import service

    source = "From 1st May to 21st June"
    for target in ("Du 1er mai au 21 juin", "Du 1re au 21e jour", "La 1ère semaine, 21 juin"):
        text, issue = service._restore_and_validate(source, target, {}, "b1", "fr")
        assert issue is None and text == target
    # The plausibility rule is French-specific.
    _, issue = service._restore_and_validate(source, "Del 1er al 21er", {}, "b1", "es")
    assert issue is None


def test_f34_rejection_maps_to_review_status_and_invalidates_memory_hits():
    from app.documents import block_status

    assert block_status._GUARD_FAILURES["IMPLAUSIBLE_TARGET_ORDINAL"] == "implausible_target"
    launcher = _launcher()
    block = {"id": "b1", "text": "From 1st May to 21st June"}
    cached = "Du 1er mai au 21er juin"
    assert launcher._hit_invalidation(block, cached, set()) == "current_guard_rejects_cached_target"
    assert (
        launcher._hit_invalidation(block, block["text"], {"IMPLAUSIBLE_TARGET_ORDINAL"})
        == "previous_guard_rejection"
    )
