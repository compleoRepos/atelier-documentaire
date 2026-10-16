from app.ai.quality.engine import _unit_occurrences


def test_french_elision_and_articles_are_not_units():
    text = "Délivré à la demande de l'intéressé ; l’expression de nos salutations, m'a dit le directeur."
    assert _unit_occurrences(text) == []


def test_units_attached_to_quantities_are_counted():
    assert _unit_occurrences("Le montant prévu est de 12.345.00euro.") == ["eur"]
    assert _unit_occurrences("capital social € 123.456.789") == ["eur"]
    assert _unit_occurrences("Poids : 5 kg, volume 2 l, remise 12 %") == ["kg", "l", "%"]
    assert _unit_occurrences("EUR 100 et 300 dirhams") == ["eur", "mad"]


def test_changed_unit_is_still_detected():
    source = _unit_occurrences("Total 5 kg")
    target = _unit_occurrences("Total 5 lb")
    assert source != target
