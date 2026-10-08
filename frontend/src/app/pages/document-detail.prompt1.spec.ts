import { describe, expect, it } from "vitest";
import { DocumentDetailPage } from "./document-detail.page";


describe("Preuves de preprocessing", () => {
  it("lit PreprocessingQualityScore et garde CER/WER non mesurés", () => {
    const page = Object.create(DocumentDetailPage.prototype) as DocumentDetailPage;
    const score = { confidence_before: 0.8, confidence_after: 0.9, improvement: 0.1,
      metric: "ocr_confidence_proxy" as const, cer: null, wer: null, validated: false as const };
    page.doc = {
      id: "test", filename: "fixture.pdf", status: "ANALYZED", created_at: "", issues: [],
      analysis: { pages: [{ number: 1, width: 100, height: 100, preprocessing: {
        version: "v1", profile: "auto", selected_variant: "original", operations: [],
        transform_source_to_processing: [], transform_processing_to_source: [], source_size: [100,100],
        processing_size: [100,100], ocr_before: {confidence: 0.8, characters: 5, blocks: 1, model: "local", version: "v1", languages: []},
        ocr_after: {confidence: 0.9, characters: 5, blocks: 1, model: "local", version: "v1", languages: []},
        PreprocessingQualityScore: score,
      }}] },
    };
    expect(page.preprocessingScore()).toEqual(score);
    expect(page.preprocessingScore()?.validated).toBe(false);
  });
  it("ne présente pas OCR natif comme exécuté", () => {
    const page = Object.create(DocumentDetailPage.prototype) as DocumentDetailPage;
    expect(page.stageDetail({id: "ocr", label: "OCR", state: "not_applicable"})).toContain("Non applicable");
  });
});
