import { TestBed } from "@angular/core/testing";
import { ActivatedRoute, Router } from "@angular/router";
import { of } from "rxjs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiService } from "../core/api.service";
import { DocumentDetail } from "../core/models";
import { ReviewPage } from "./review.page";

const documentFixture: DocumentDetail = {
  id: "prompt1-document",
  filename: "source.pdf",
  status: "REVIEW_REQUIRED",
  created_at: "2026-10-08T00:00:00Z",
  review_version: 3,
  issues: [],
  analysis: { pages: [{ number: 1, width: 300, height: 200, blocks: [] }] },
  translation: { translations: {}, issues: [], untranslated_blocks: [] },
};

describe("prompt 1 revue preprocessing", () => {
  let page: ReviewPage;
  let api: { document: ReturnType<typeof vi.fn>; preview: ReturnType<typeof vi.fn> };
  let createUrl: ReturnType<typeof vi.fn>;
  let revokeUrl: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    api = {
      document: vi.fn().mockReturnValue(of(documentFixture)),
      preview: vi.fn().mockImplementation((_id, kind) => of(new Blob([kind]))),
    };
    createUrl = vi.fn().mockReturnValue("blob:prompt1");
    revokeUrl = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createUrl });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeUrl });
    TestBed.configureTestingModule({
      providers: [
        { provide: ApiService, useValue: api },
        { provide: ActivatedRoute, useValue: { snapshot: { paramMap: { get: () => documentFixture.id } } } },
        { provide: Router, useValue: { navigate: vi.fn() } },
      ],
    });
    page = TestBed.runInInjectionContext(() => new ReviewPage());
  });

  afterEach(() => page.ngOnDestroy());

  it("demande l'image enhanced avec la version de revue authentifiée", () => {
    expect(api.preview).toHaveBeenCalledWith(documentFixture.id, "enhanced", 1, 3);
    expect(page.images.enhanced).toBe("blob:prompt1");
  });

  it("révoque les quatre blob URLs quand la sélection change ou la page se détruit", () => {
    page.toUrl(new Blob(["manual"]));
    page.revokeUrls();
    expect(revokeUrl).toHaveBeenCalled();
    expect(page.images).toEqual({ original: null, enhanced: null, translated: null, diff: null });
  });
});
