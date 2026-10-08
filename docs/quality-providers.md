# Quality providers

`app.ai.quality.providers` contains the concrete providers that may be passed to
`evaluate_quality`. Both are typed subclasses of the existing
`app.ai.quality.engine.QualityProvider`; a plain callback is not an accepted
quality capability.

## LocalEmbeddingProvider

`LocalEmbeddingProvider` is an **offline** Hugging Face encoder. Its
constructor requires an `assets_dir` and `model_version`. When a tokenizer and
model are not injected by a local adapter/test it loads both with:

```python
AutoTokenizer.from_pretrained(
    assets_dir, local_files_only=True, trust_remote_code=False
)
AutoModel.from_pretrained(
    assets_dir, local_files_only=True, trust_remote_code=False
)
```

There is no model download or public fallback. `torch` is imported only when a
real transformer forward pass is needed. `health_check()` returns `None` when
that optional runtime is unavailable instead of claiming a healthy provider.

### Bounded semantic agreement

The synchronous engine contract is:

```python
provider(text, expected, max_context=32768) -> float | None
```

`max_context` must be an integer in `1..32768`. Text is split at sentence
boundaries and contiguous sentences are grouped into windows. A sentence that
cannot fit in the selected budget makes the measurement unavailable; it is not
silently cut. Each window is mean-pooled, optionally projected, and compared
with cosine similarity. Window scores are averaged into the
`semantic_agreement_cosine` score in `[0, 1]`.

This is a **relative semantic agreement measurement**, not a probability, not a
translation certification, and not a measure of factual faithfulness. In
particular, a high cosine score must not replace the engine's independent
protected-entity checks for dates, amounts, codes, names, or other invariants.
Use `provider.evaluate(...)` for the auditable score/provenance record.

Provenance includes the declared scope (`local`), model version, device,
assets directory, and a hash of local asset metadata. The
`no_public_model_calls` field records the provider's declared boundary; it is
not a proof about an external deployment.

## PrivateQwenJudgeProvider

`PrivateQwenJudgeProvider` is a synchronous adapter for an explicitly private,
OpenAI-compatible `/chat/completions` endpoint. It does **not** read
`OPENAI_*` variables, discover a proxy, or fall back to a public service. The
API key, if used, is an explicit constructor argument.

Before construction and immediately before every request it reuses the
translation service's private URL guard:

- `http`/`https` only, with no URL credentials;
- exact host allowlist;
- DNS resolution checked against private, loopback, or link-local addresses;
- no redirects; and
- `httpx.Client(trust_env=False, follow_redirects=False)`.

The tokenizer is also local-only (`local_files_only=True`,
`trust_remote_code=False`). Chat-template token counts include a schema
reserve, the requested output budget, and a safety margin. The complete
request must fit in the hard `32768`-token ceiling or the provider returns
`None`.

### Original source and human reference

`evaluate(original_source, candidate, expected_reference)` is the full judge
API. The original source is required for faithfulness evidence. The expected
French/reference translation is passed as a separate field and is used for
reference agreement; it is not silently treated as source truth. The result
cannot claim faithfulness when the original source is absent.

The engine's existing two-text callback contract has no original source. The
provider therefore uses that contract only for a bounded reference-agreement
measurement, while direct `evaluate` remains the path for source-grounded
judging.

### Strict result shape

A successful private response has exactly these top-level fields (the optional
`coverage` may be absent or `null`):

```json
{
  "scores": {
    "fidelity": 0.0,
    "coherence": 0.0,
    "terminology": 0.0,
    "context": 0.0,
    "style": 0.0
  },
  "citations": [
    {
      "source": [0, 12],
      "candidate": [0, 12],
      "proof": "bounded evidence text"
    }
  ],
  "contradictions": [],
  "coverage": null
}
```

All five scores must be finite numbers in `[0, 1]`; booleans, `NaN`, and
infinity are rejected. Citation and contradiction spans must be non-empty and
within the supplied original-source/candidate lengths. Every citation needs a
textual proof and every contradiction needs a reason. Missing coverage is
preserved as `coverage: null` and `coverage_complete: false`; absence of a
coverage claim is never promoted to exhaustive proof.

## Engine usage

```python
from app.ai.quality.engine import evaluate_quality
from app.ai.quality.providers import LocalEmbeddingProvider

provider = LocalEmbeddingProvider(
    "/srv/private-models/encoder-v1",
    model_version="encoder-v1",
    device="cpu",
)
result = evaluate_quality(
    ir,
    translations,
    reference=human_reference,
    options={"embedding_provider": provider},
)
```

The quality engine recognizes the object through the typed
`QualityProvider` contract. Provider failures return an unavailable score
(`None`) and leave the engine in review/fail-closed handling. They do not
manufacture a passing quality score.
