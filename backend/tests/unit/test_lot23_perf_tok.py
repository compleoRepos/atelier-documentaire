"""LOT 2.3 Phase B — D-PERF-TOK : le tokenizer n'est plus rechargé à chaque document.

Le cache est par processus, indexé par le chemin réel et par (nom, taille, date) de chaque
fichier : toute modification sur disque provoque un rechargement. Le tokenizer de test est
fabriqué localement (aucun téléchargement).
"""

from __future__ import annotations

import json
import os

import pytest

tokenizers = pytest.importorskip("tokenizers")
pytest.importorskip("transformers")

from app.ai.translation import service  # noqa: E402


def _make_tokenizer(directory, vocabulary=("[UNK]", "salaire", "brut")) -> str:
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace

    directory.mkdir(parents=True, exist_ok=True)
    model = WordLevel({word: i for i, word in enumerate(vocabulary)}, unk_token="[UNK]")
    tokenizer = Tokenizer(model)
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer.save(str(directory / "tokenizer.json"))
    (directory / "tokenizer_config.json").write_text(
        json.dumps({"tokenizer_class": "PreTrainedTokenizerFast", "unk_token": "[UNK]"}),
        encoding="utf-8",
    )
    return str(directory)


@pytest.fixture(autouse=True)
def _empty_cache(monkeypatch):
    monkeypatch.setattr(service, "_TOKENIZER_CACHE", {})


def test_same_files_reuse_the_loaded_tokenizer(tmp_path):
    path = _make_tokenizer(tmp_path / "tok")
    first = service._load_local_tokenizer(path)
    second = service._load_local_tokenizer(path)
    assert first is second
    assert first("salaire brut")["input_ids"] == [1, 2]


def test_changed_file_loads_the_tokenizer_again(tmp_path):
    path = _make_tokenizer(tmp_path / "tok")
    first = service._load_local_tokenizer(path)
    _make_tokenizer(tmp_path / "tok", vocabulary=("[UNK]", "brut", "salaire", "net"))
    stat = os.stat(os.path.join(path, "tokenizer.json"))
    os.utime(os.path.join(path, "tokenizer.json"), ns=(stat.st_atime_ns, stat.st_mtime_ns + 10**9))
    second = service._load_local_tokenizer(path)
    assert second is not first
    assert second("salaire brut")["input_ids"] == [2, 1]


def test_hash_is_still_computed_from_files(tmp_path):
    path = _make_tokenizer(tmp_path / "tok")
    tokenizer = service._load_local_tokenizer(path)
    before = service._tokenizer_hash(tokenizer, path)
    with open(os.path.join(path, "tokenizer_config.json"), "a", encoding="utf-8") as handle:
        handle.write("\n")
    assert service._tokenizer_hash(service._load_local_tokenizer(path), path) != before


def test_cache_is_bounded(tmp_path):
    for index in range(service._TOKENIZER_CACHE_MAX + 2):
        service._load_local_tokenizer(_make_tokenizer(tmp_path / f"tok{index}"))
    assert len(service._TOKENIZER_CACHE) <= service._TOKENIZER_CACHE_MAX
