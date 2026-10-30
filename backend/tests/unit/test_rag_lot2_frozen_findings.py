"""F-L2-03 : caractérisation d'un défaut du constructeur de contexte GELÉ (non corrigé au LOT 2).

``ContextPackBuilder.relevant_context`` découpe le bloc source sur les espaces seulement : un jeton
suivi d'une ponctuation (``Bruttogehalt:``) ne se retrouve pas dans l'entrée de glossaire, qui est
alors retirée du contexte envoyé au moteur. Le correctif modifie un fichier de la fermeture
d'empreinte historique : il exige une branche séparée et une validation explicite.
Le test ``xfail(strict=True)`` échouera dès que le défaut sera corrigé, pour forcer sa mise à jour.
"""

from __future__ import annotations

import pytest

from app.ai.context.builder import ContextPackBuilder

GLOSSARY = {"glossary": [{"source": "Bruttogehalt", "target": "rémunération brute"}]}


def _terms_sent(text: str) -> list:
    builder = ContextPackBuilder(tokenizer=None, max_tokens=10**9)
    chunk = {"blocks": [{"id": "b001", "text": text}]}
    return builder.relevant_context({"pages": []}, chunk, GLOSSARY)["terms"]


def test_glossary_entry_is_sent_when_the_word_stands_alone():
    assert _terms_sent("Bruttogehalt 3.831,25 EUR") == GLOSSARY["glossary"]


@pytest.mark.xfail(strict=True, reason="F-L2-03 : ponctuation collée au jeton (fichier gelé)")
def test_glossary_entry_is_sent_when_followed_by_punctuation():
    assert _terms_sent("Bruttogehalt: 3.831,25 EUR") == GLOSSARY["glossary"]
