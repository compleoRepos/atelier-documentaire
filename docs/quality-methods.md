# Quality engine v2 — methods and evidence contract

This lot is deliberately independent of the document pipeline. The document agent
calls `app.ai.quality.engine.evaluate_quality(ir, translations, render_result,
reference, options)` once it has assembled the IR and reconstruction evidence.
No public model, proxy, remote download, or dataset original is read by this code.

## Result and fail-closed policy

The result contains `ocr_score`, `translation_score`, `semantic_score`,
`layout_score`, `visual_score`, `status`, `issues`, `critical_entity_errors`,
`hallucination_errors`, `reference_status`, `provenance`, and `coverage`.
Scores are in `[0, 1]`; a score is `None` when the evidence needed for that
method is absent. Missing proof produces `REVIEW_REQUIRED`, never an artificial
100% or PASS. Measured critical invariant or protected-region failures produce
`FAIL`.

## OCR

OCR is scored only against `ocr_text` carrying an explicit `ocr_validated: true`
or `ocr_validation: human|signed|validated` claim. The result also retains
CER/WER in `quality.ocr`, but those are lexical OCR error rates only. A
translation approval does not attest to the OCR transcript.

## Translation and semantics

A signed/human rubric (`reference.rubric`, `quality_rubric`, or `human_review`)
can score dimensions such as fidelity, coherence, terminology, context, style,
and hallucination control. It must carry reviewer/validation or an explicit
signed/approved claim. When no rubric exists, `translation_score` is only
validated-reference lexical agreement; it is labelled as such in provenance.

`semantic_score` is exact normalized agreement with a validated target reference
(1 or 0). An optional embedding or judge callable is accepted only when marked
`local` or `private`, receives the configured context bounded by 32768, and is
never loaded or called over a public network. CER/WER are never used as semantic
scores.

## Entities and hallucinations

`extract_entities` reports occurrences, offsets, type and provenance for names,
companies, numbers, dates, amounts, codes, IBANs, phones, email, addresses and
other stable invariants. Signed annotations are preferred. Regex coverage is
explicitly limited and is not a claim of complete NER. Comparison preserves
multiplicity and order, so a changed date, sign, name or second occurrence is
not hidden. Units and referenced assertions are also compared; missing or added
facts become hallucination issues. Real documents must provide `entities` /
`protected_entities` and, where applicable, `assertions` in the IR or signed
reference for exhaustive coverage.

## Visual and layout evidence

`app.ai.vision.scorer.score_visual` combines:

- page count, blank-page and disappeared-region checks;
- protected-region integrity results;
- finite geometry metrics (blocks, IoU/displacement, overlap/clipping and page dimensions);
- table/cell/merge/reading-order/image/signature structure metrics;
- optional source/candidate previews compared outside bounded text masks.

A text mask must have finite page coordinates and may not exceed the configured
fraction (default 35%) of a page. Masking an entire page is rejected. Raw pixel
difference is not exposed as a quality score. `render_result` should provide:

```python
{
    "source_page_count": 2,
    "translated_page_count": 2,
    "geometry_metrics": {"blocks": 0.98, "clipping": 1.0},
    "structure_metrics": {"tables": 1.0, "merges": 1.0, "reading_order": 1.0},
    "protected_region_results": [{"page": 1, "id": "signature", "preserved": True}],
    "text_masks": [{"page": 1, "bbox": [40, 80, 300, 120]}],
    "source_previews": ["/private/work/original-001.png"],
    "translated_previews": ["/private/work/candidate-001.png"],
    "provenance": "private-renderer-v2",
}
```

## Inputs required from the document agent

- Stable IR block IDs and source text (`pages[*].blocks[*]` or `blocks`, or
  `source_text`), with every translated ID represented in `translations`.
- Explicitly validated OCR transcript when an OCR metric is desired.
- Signed target reference or signed rubric for reference-based translation and
  semantic dimensions; a translation approval alone is not OCR evidence.
- Entity/protected annotations with occurrence identity where regex extraction
  is insufficient, plus assertion records for domain facts.
- Reconstruction previews, page counts, finite geometry/structure metrics and
  protected-region check results for visual/layout metrics.

The module does not promote private dataset files to references. Golden or bank
acceptance remains a separate human/audited step.
