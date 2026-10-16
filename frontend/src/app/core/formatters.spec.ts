import {
  buildCorrectionPayload,
  formatMetric,
  statusClass,
  statusLabel,
} from "./formatters";

describe("formatters de l’atelier documentaire", () => {
  it("affiche une mesure absente sans inventer de score", () => {
    expect(formatMetric(null)).toBe("Non mesuré");
    expect(formatMetric(0.834)).toBe("83 %");
  });
  it("traduit les statuts contractuels en classe et libellé lisibles", () => {
    expect(statusLabel("REVIEW_REQUIRED")).toBe("Revue requise");
    expect(statusClass("REVIEW_REQUIRED")).toBe("status-review-required");
  });
  it("construit un payload de corrections nettoyé", () => {
    expect(
      buildCorrectionPayload({ block_a: "  Texte corrigé  ", block_b: "   " })
    ).toEqual({ block_a: "  Texte corrigé  " });
  });
});
