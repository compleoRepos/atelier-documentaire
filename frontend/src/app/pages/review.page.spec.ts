import { TestBed } from "@angular/core/testing";
import { ActivatedRoute, Router } from "@angular/router";
import { of, throwError } from "rxjs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiService } from "../core/api.service";
import { DocumentDetail } from "../core/models";
import { ReviewPage } from "./review.page";

function fixture(version = 1): DocumentDetail {
  return {
    id: "synthetic-document",
    filename: "synthetic.pdf",
    status: "REVIEW_REQUIRED",
    created_at: "2026-10-07T12:00:00Z",
    review_version: version,
    issues: [],
    protected_entities: [],
    protected_regions: [],
    analysis: {
      pages: [
        {
          number: 1,
          width: 595,
          height: 842,
          blocks: [
            {
              id: "block-1",
              page: 1,
              kind: "paragraph",
              text: "Attestation de travail",
            },
          ],
        },
      ],
    },
    translation: {
      translations: { "block-1": "Attestation de travail" },
      issues: [],
      untranslated_blocks: [],
    },
  };
}

describe("revue documentaire versionnée", () => {
  let page: ReviewPage;
  let api: {
    document: ReturnType<typeof vi.fn>;
    preview: ReturnType<typeof vi.fn>;
    review: ReturnType<typeof vi.fn>;
  };
  beforeEach(() => {
    api = {
      document: vi.fn().mockReturnValue(of(fixture())),
      preview: vi
        .fn()
        .mockReturnValue(
          throwError(() => new Error("Pas d'image dans ce test unitaire"))
        ),
      review: vi
        .fn()
        .mockReturnValue(
          of({ ...fixture(2), analysis: undefined, translation: undefined })
        ),
    };
    TestBed.configureTestingModule({
      providers: [
        { provide: ApiService, useValue: api },
        {
          provide: ActivatedRoute,
          useValue: {
            snapshot: { paramMap: { get: () => "synthetic-document" } },
          },
        },
        {
          provide: Router,
          useValue: { navigate: vi.fn().mockResolvedValue(true) },
        },
      ],
    });
    page = TestBed.runInInjectionContext(() => new ReviewPage());
  });
  afterEach(() => page.ngOnDestroy());

  it("transmet la version effectivement affichée à l'API", () => {
    page.attestReview = true;
    expect(page.payload("approve")?.expected_version).toBe(1);
  });

  it("transmet séparément la transcription OCR attestée et la rubrique humaine", () => {
    page.attestReview = true;
    page.attestOcr = true;
    page.ocrText = "Attestation de travail";
    page.promoteGolden = true;
    page.qualityRubricDraft = {
      fidelity: 0.91,
      coherence: 0.87,
      terminology: 0.8,
      context: 0.76,
      style: 0.72,
    };
    expect(page.payload("approve")).toMatchObject({
      expected_version: 1,
      ocr_text: "Attestation de travail",
      attest_ocr: true,
      quality_rubric: page.qualityRubricDraft,
    });
  });

  it("n'invente aucun score humain si une dimension manque", () => {
    page.attestReview = true;
    page.promoteGolden = true;
    expect(page.payload("approve")).toBeNull();
    expect(page.message).toContain("cinq scores humains");
  });

  it("bloque l'approbation de corrections non enregistrées", () => {
    page.attestReview = true;
    page.setCorrection("block-1", "Justificatif de travail");
    expect(page.payload("approve")).toBeNull();
    expect(page.message).toContain("Enregistrez");
    expect(api.review).not.toHaveBeenCalled();
  });

  it("recharge l'analyse complète et réinitialise l'attestation après correction", () => {
    const corrected = fixture(2);
    corrected.translation!.translations["block-1"] = "Justificatif de travail";
    api.document.mockReturnValue(of(corrected));
    page.setCorrection("block-1", "Justificatif de travail");
    page.attestReview = true;
    page.submit("correct");
    expect(api.document).toHaveBeenCalledTimes(2);
    expect(page.allBlocks()).toHaveLength(1);
    expect(page.corrections["block-1"]).toBe("Justificatif de travail");
    expect(page.doc?.review_version).toBe(2);
    expect(page.attestReview).toBe(false);
  });

  it("refuse la suppression silencieuse d'un bloc par une valeur vide", () => {
    page.setCorrection("block-1", "");
    expect(page.payload("correct")).toBeNull();
    expect(page.message).toContain("correction vide");
  });
  it("signale XLSX/PPTX comme vérifiés nativement, sans preuve visuelle", () => {
    expect(page.isOfficeSheetOrSlides("synthetic.xlsx")).toBe(true);
    expect(page.isOfficeSheetOrSlides("SYNTHETIC.PPTX")).toBe(true);
    expect(page.isOfficeSheetOrSlides("synthetic.docx")).toBe(false);
    expect(page.isOfficeSheetOrSlides("synthetic.pdf")).toBe(false);
    expect(page.isOfficeSheetOrSlides("synthetic.xlsx.pdf")).toBe(false);
  });
});
