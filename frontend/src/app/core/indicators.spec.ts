import { allIssues, controlIndicators } from "./indicators";
import { DocumentDetail } from "./models";

function doc(overrides: Partial<DocumentDetail> = {}): DocumentDetail {
  return {
    id: "doc-1",
    filename: "synthetic.pdf",
    status: "REVIEW_REQUIRED",
    created_at: "2026-10-14T00:00:00Z",
    issues: [],
    ...overrides,
  } as DocumentDetail;
}

function translated(extra: Record<string, unknown> = {}) {
  return {
    translations: {},
    issues: [],
    untranslated_blocks: [],
    block_status: {
      summary: {
        blocks: { TRANSLATED: 8, FAILED: 1, UNCERTAIN: 2, NOT_PROCESSED: 0, PRESERVED_INTENTIONALLY: 3, NOT_TRANSLATABLE: 1 },
        chars: { TRANSLATED: 996, FAILED: 2, UNCERTAIN: 2, NOT_PROCESSED: 0, PRESERVED_INTENTIONALLY: 50, NOT_TRANSLATABLE: 7 },
        reasons: { "TRANSLATED:translated_and_placed": 8, "FAILED:render_overflow": 1, "UNCERTAIN:ocr_unreliable": 2 },
      },
    },
    translation_telemetry: {
      provider: "interim",
      requests_sent: 2,
      generation_mode: "MIXED",
      block_provenance: {
        blocks: {
          a: { origin: "MODEL_CALL" },
          b: { origin: "MODEL_CALL" },
          c: { origin: "TRANSLATION_MEMORY" },
          d: { origin: "NOT_SENT" },
        },
      },
    },
    ...extra,
  };
}

function byKey(d: DocumentDetail) {
  return Object.fromEntries(controlIndicators(d).map(item => [item.key, item]));
}

describe("indicateurs de contrôle RUN28", () => {
  it("présente les six indicateurs dans l’ordre prioritaire", () => {
    expect(controlIndicators(doc()).map(item => item.key)).toEqual([
      "coverage",
      "critical",
      "reconstruction",
      "review",
      "provenance",
      "status",
    ]);
  });

  it("n’invente aucune réussite quand rien n’est mesuré", () => {
    const items = byKey(doc({ status: "ANALYZED" }));
    expect(items["coverage"].value).toBe("Non mesuré");
    expect(items["coverage"].tone).toBe("unknown");
    expect(items["reconstruction"].value).toBe("Non mesuré");
    expect(items["review"].value).toBe("Non mesuré");
    expect(items["provenance"].value).toBe("Non mesuré");
    expect(items["critical"].tone).toBe("unknown");
    expect(items["status"].tone).toBe("unknown");
  });

  it("arrondit la couverture vers le bas et compte les blocs non traduits", () => {
    const items = byKey(doc({ translation: translated() as never }));
    // 996 / 1000 = 99,6 % -> 99,6 % affiché, jamais 100 %
    expect(items["coverage"].value).toBe("99,6 %");
    expect(items["coverage"].tone).toBe("warn");
    expect(items["coverage"].detail).toContain("3 blocs non traduit(s)");
  });

  it("n’arrondit jamais vers 100 % (9 999 / 10 000 -> 99,9 %)", () => {
    const t = translated();
    (t.block_status.summary.chars as Record<string, number>) = { TRANSLATED: 9999, FAILED: 1 };
    const items = byKey(doc({ translation: t as never }));
    expect(items["coverage"].value).toBe("99,9 %");
    expect(items["coverage"].tone).toBe("warn");
  });

  it("n’affiche 100 % que si tout le texte à traduire est traduit", () => {
    const t = translated();
    (t.block_status.summary.chars as Record<string, number>) = { TRANSLATED: 10, PRESERVED_INTENTIONALLY: 4 };
    const items = byKey(doc({ translation: t as never }));
    expect(items["coverage"].value).toBe("100 %");
    expect(items["coverage"].tone).toBe("ok");
  });

  it("signale les erreurs critiques sans les neutraliser par une approbation", () => {
    const critical = { code: "ENTITY_DIGITS_MISMATCH", severity: "critical", message: "m", block_id: "a" };
    const d = doc({
      status: "APPROVED",
      issues: [critical],
      translation: translated({ issues: [critical, { code: "LAYOUT_OVERFLOW", severity: "critical", message: "o" }] }) as never,
    });
    const items = byKey(d);
    expect(allIssues(d).length).toBe(2); // doublon document/traduction éliminé
    expect(items["critical"].value).toBe("2");
    expect(items["critical"].tone).toBe("bad");
    expect(items["critical"].detail).toContain("ENTITY_DIGITS_MISMATCH ×1");
    expect(items["status"].tone).toBe("warn");
    expect(items["status"].detail).toContain("malgré 2 erreurs critique(s)");
  });

  it("compte les échecs de rendu du fichier produit", () => {
    const items = byKey(doc({ translation: translated() as never }));
    expect(items["reconstruction"].value).toBe("1 échec de rendu");
    expect(items["reconstruction"].tone).toBe("bad");
  });

  it("ne présente pas un fichier Office vérifié nativement comme visuellement prouvé", () => {
    const t = translated({ native_verification: { status: "VERIFIED", visual_proof: "NOT_AVAILABLE" } });
    (t.block_status.summary.reasons as Record<string, number>) = { "TRANSLATED:translated_and_placed": 8 };
    const items = byKey(doc({ translation: t as never }));
    expect(items["reconstruction"].tone).toBe("warn");
    expect(items["reconstruction"].value).toBe("Texte vérifié, visuel non prouvé");
    expect(items["reconstruction"].detail).toContain("preuve visuelle non disponible");
  });

  it("marque une vérification native en échec comme échec", () => {
    const t = translated({ native_verification: { status: "FAILED", visual_proof: "NOT_AVAILABLE" } });
    (t.block_status.summary.reasons as Record<string, number>) = {};
    expect(byKey(doc({ translation: t as never }))["reconstruction"].tone).toBe("bad");
  });

  it("distingue vérification automatique et validation humaine", () => {
    const items = byKey(doc({ translation: translated() as never }));
    expect(items["review"].value).toBe("3 blocs");
    expect(items["review"].detail).toContain("ne remplace pas la validation humaine");
    expect(items["status"].detail).toContain("Aucune validation humaine enregistrée");
    expect(byKey(doc({ status: "APPROVED", translation: translated() as never }))["status"].detail).toBe(
      "Validé par un relecteur humain."
    );
  });

  it("expose la provenance par bloc et le nombre de requêtes", () => {
    const items = byKey(doc({ translation: translated() as never }));
    expect(items["provenance"].value).toBe("Interim (temporaire, hors cloud privé)");
    expect(items["provenance"].detail).toContain("appel modèle 2");
    expect(items["provenance"].detail).toContain("mémoire 1");
    expect(items["provenance"].detail).toContain("non envoyé 1");
    expect(items["provenance"].detail).toContain("2 requêtes au modèle");
  });

  it("ignore les compteurs invalides au lieu de les additionner", () => {
    const t = translated();
    (t.block_status.summary.chars as Record<string, unknown>) = { TRANSLATED: "999", FAILED: -4, UNCERTAIN: 5 };
    const items = byKey(doc({ translation: t as never }));
    expect(items["coverage"].value).toBe("0 %");
    expect(items["coverage"].tone).toBe("bad");
  });
});
