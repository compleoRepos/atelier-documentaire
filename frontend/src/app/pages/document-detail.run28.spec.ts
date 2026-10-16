import { TestBed } from "@angular/core/testing";
import { ActivatedRoute, convertToParamMap, provideRouter } from "@angular/router";
import { of } from "rxjs";
import { describe, expect, it, vi } from "vitest";
import { ApiService } from "../core/api.service";
import { DocumentDetailPage } from "./document-detail.page";

describe("Fiche document RUN28 — synthèse de contrôle rendue", () => {
  it("affiche les six indicateurs dans le DOM, inconnus compris", async () => {
    const detail = {
      id: "doc-1",
      filename: "synthetic.xlsx",
      status: "REVIEW_REQUIRED",
      created_at: "2026-10-14T00:00:00Z",
      issues: [{ code: "OFFICE_VISUAL_PROOF_UNAVAILABLE", severity: "warning", message: "m" }],
      translation: {
        translations: {},
        issues: [],
        untranslated_blocks: [],
        block_status: {
          summary: {
            blocks: { TRANSLATED: 3, FAILED: 1 },
            chars: { TRANSLATED: 30, FAILED: 10 },
            reasons: { "TRANSLATED:translated_and_placed": 3, "FAILED:model_returned_source": 1 },
          },
        },
        native_verification: { status: "VERIFIED", visual_proof: "NOT_AVAILABLE" },
      },
    };
    const api = { document: vi.fn().mockReturnValue(of(detail)) };
    TestBed.configureTestingModule({
      imports: [DocumentDetailPage],
      providers: [
        provideRouter([]),
        { provide: ApiService, useValue: api },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: convertToParamMap({ id: "doc-1" }) } } },
      ],
    });
    const fixture = TestBed.createComponent(DocumentDetailPage);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    const items = Array.from(root.querySelectorAll("[data-indicator]"));
    expect(items.map(item => item.getAttribute("data-indicator"))).toEqual([
      "coverage",
      "critical",
      "reconstruction",
      "review",
      "provenance",
      "status",
    ]);
    const text = (key: string) =>
      root.querySelector(`[data-indicator="${key}"]`)?.textContent?.replace(/\s+/g, " ").trim() ?? "";
    expect(text("coverage")).toContain("75 %");
    expect(text("reconstruction")).toContain("Texte vérifié, visuel non prouvé");
    expect(text("provenance")).toContain("Non mesuré");
    expect(text("status")).toContain("Aucune validation humaine enregistrée");
    expect(root.querySelector(".control-note")?.textContent).toContain("ne constituent pas une validation humaine");
  });
});
