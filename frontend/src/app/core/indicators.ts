import { DocumentDetail, Issue } from "./models";
import { statusLabel } from "./formatters";

/**
 * RUN28 — the six control indicators shown first on a document page.
 *
 * Pure function of the API payload. Rules:
 * - a missing measurement is displayed as "Non mesuré" (tone "unknown"),
 *   never as a success;
 * - percentages are floored, so 99.6 % is never shown as 100 %;
 * - an automatic verification is never presented as a human validation;
 * - no global score is computed here: a critical error is always shown on
 *   its own and cannot be offset by other indicators.
 */
export type IndicatorTone = "ok" | "warn" | "bad" | "info" | "unknown";
export type IndicatorKey =
  | "coverage"
  | "critical"
  | "reconstruction"
  | "review"
  | "provenance"
  | "status";
export interface ControlIndicator {
  key: IndicatorKey;
  label: string;
  value: string;
  detail: string;
  tone: IndicatorTone;
}

type Counts = Record<string, number>;
const UNKNOWN = "Non mesuré";
const TO_TRANSLATE = ["TRANSLATED", "FAILED", "UNCERTAIN", "NOT_PROCESSED"];
const NEEDS_REVIEW = ["FAILED", "UNCERTAIN", "NOT_PROCESSED"];
const ORIGIN_LABELS: Record<string, string> = {
  MODEL_CALL: "appel modèle",
  TRANSLATION_MEMORY: "mémoire",
  NOT_SENT: "non envoyé",
};
const PROVIDER_LABELS: Record<string, string> = {
  interim: "Interim (temporaire, hors cloud privé)",
  private: "moteur privé",
  offline: "hors ligne (mémoire/glossaire)",
};

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function counts(value: unknown): Counts | null {
  const source = record(value);
  if (!source) return null;
  const out: Counts = {};
  for (const [key, raw] of Object.entries(source)) {
    if (typeof raw === "number" && Number.isFinite(raw) && raw >= 0) out[key] = raw;
  }
  return out;
}

function sum(source: Counts, keys: string[]): number {
  return keys.reduce((total, key) => total + (source[key] ?? 0), 0);
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n > 1 ? "s" : ""}`;
}

function blockSummary(doc: DocumentDetail): {
  blocks: Counts | null;
  chars: Counts | null;
  reasons: Counts | null;
} {
  const summary = record(record(doc.translation?.["block_status"])?.["summary"]);
  return {
    blocks: counts(summary?.["blocks"]),
    chars: counts(summary?.["chars"]),
    reasons: counts(summary?.["reasons"]),
  };
}

/** Issues from the document and the translation result, de-duplicated. */
export function allIssues(doc: DocumentDetail): Issue[] {
  const seen = new Set<string>();
  const out: Issue[] = [];
  const pools = [doc.issues ?? [], (doc.translation?.issues as Issue[] | undefined) ?? []];
  for (const pool of pools) {
    for (const issue of pool) {
      if (!issue || typeof issue.code !== "string") continue;
      const key = `${issue.code}|${issue.block_id ?? ""}|${issue.severity}|${issue.message}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(issue);
    }
  }
  return out;
}

function coverage(doc: DocumentDetail): ControlIndicator {
  const base = { key: "coverage" as const, label: "Couverture de traduction mesurée" };
  const { chars, blocks } = blockSummary(doc);
  if (!chars) {
    return { ...base, value: UNKNOWN, detail: "Aucun statut par bloc disponible.", tone: "unknown" };
  }
  const expected = sum(chars, TO_TRANSLATE);
  const translated = chars["TRANSLATED"] ?? 0;
  const pending = blocks ? sum(blocks, NEEDS_REVIEW) : null;
  const justified = sum(chars, ["PRESERVED_INTENTIONALLY", "NOT_TRANSLATABLE"]);
  if (expected === 0) {
    return {
      ...base,
      value: "Aucun texte à traduire",
      detail: `${justified} caractère(s) conservé(s) avec justification ; rien n’a été mesuré comme à traduire.`,
      tone: "unknown",
    };
  }
  const pct = Math.floor((translated / expected) * 1000) / 10;
  return {
    ...base,
    value: `${pct.toLocaleString("fr-FR")} %`,
    detail:
      `${translated} / ${expected} caractères à traduire traduits et placés` +
      (pending === null ? "" : ` ; ${plural(pending, "bloc")} non traduit(s) signalé(s)`) +
      ` ; ${justified} caractère(s) conservé(s) avec justification.`,
    tone: translated === expected ? "ok" : pct >= 50 ? "warn" : "bad",
  };
}

function critical(doc: DocumentDetail): ControlIndicator {
  const base = { key: "critical" as const, label: "Erreurs critiques" };
  const items = allIssues(doc).filter(issue => issue.severity === "critical");
  if (!items.length) {
    return {
      ...base,
      value: "0",
      detail: doc.translation
        ? "Aucune erreur critique détectée automatiquement (ce n’est pas une validation humaine)."
        : "Aucune erreur critique à l’analyse ; traduction non exécutée.",
      tone: doc.translation ? "ok" : "unknown",
    };
  }
  const byCode = new Map<string, number>();
  for (const issue of items) byCode.set(issue.code, (byCode.get(issue.code) ?? 0) + 1);
  const top = [...byCode.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .slice(0, 3)
    .map(([code, n]) => `${code} ×${n}`)
    .join(" · ");
  return { ...base, value: String(items.length), detail: top, tone: "bad" };
}

function reconstruction(doc: DocumentDetail): ControlIndicator {
  const base = { key: "reconstruction" as const, label: "Qualité de reconstruction" };
  const { reasons } = blockSummary(doc);
  const native = record(doc.translation?.["native_verification"]);
  if (!reasons && !native) {
    return { ...base, value: UNKNOWN, detail: "Aucune vérification du fichier produit disponible.", tone: "unknown" };
  }
  const renderFailures = reasons
    ? Object.entries(reasons)
        .filter(([reason]) => reason.startsWith("FAILED:render_"))
        .reduce((total, [, n]) => total + n, 0)
    : 0;
  const parts: string[] = [];
  let tone: IndicatorTone = renderFailures ? "bad" : "ok";
  if (reasons) {
    parts.push(
      renderFailures
        ? `${plural(renderFailures, "bloc")} traduit(s) non reconstruit(s) (débordement, encre résiduelle, masque…)`
        : "Aucun échec de reconstruction détecté sur le fichier produit"
    );
  }
  if (native) {
    const status = String(native["status"] ?? "INCONNU");
    parts.push(`Vérification native du fichier : ${status}`);
    if (status !== "VERIFIED") tone = "bad";
    if (native["visual_proof"] === "NOT_AVAILABLE") {
      parts.push("preuve visuelle non disponible (mise en page à contrôler)");
      if (tone === "ok") tone = "warn";
    }
  }
  const value = renderFailures
    ? `${plural(renderFailures, "échec")} de rendu`
    : tone === "warn"
      ? "Texte vérifié, visuel non prouvé"
      : tone === "bad"
        ? "Échec de vérification"
        : "Aucun échec détecté";
  return { ...base, value, detail: parts.join(" ; ") + ".", tone };
}

function review(doc: DocumentDetail): ControlIndicator {
  const base = { key: "review" as const, label: "Éléments à revoir par un humain" };
  const { blocks } = blockSummary(doc);
  const automatic = "Une vérification automatique ne remplace pas la validation humaine.";
  if (!blocks) {
    return {
      ...base,
      value: UNKNOWN,
      detail: doc.status === "REVIEW_REQUIRED" ? `Revue requise. ${automatic}` : automatic,
      tone: "unknown",
    };
  }
  const pending = sum(blocks, NEEDS_REVIEW);
  const detail =
    `${blocks["FAILED"] ?? 0} en échec · ${blocks["UNCERTAIN"] ?? 0} incertain(s) · ` +
    `${blocks["NOT_PROCESSED"] ?? 0} non traité(s). ${automatic}`;
  return {
    ...base,
    value: plural(pending, "bloc"),
    detail,
    tone: pending ? "warn" : doc.status === "APPROVED" ? "ok" : "info",
  };
}

function provenance(doc: DocumentDetail): ControlIndicator {
  const base = { key: "provenance" as const, label: "Provenance de la traduction" };
  const telemetry = record(doc.translation?.["translation_telemetry"]);
  if (!telemetry) {
    return { ...base, value: UNKNOWN, detail: "Aucune télémétrie de traduction.", tone: "unknown" };
  }
  const provider = String(telemetry["provider"] ?? doc.provider_requested ?? "inconnu");
  const blocks = record(record(telemetry["block_provenance"])?.["blocks"]);
  const origins = new Map<string, number>();
  for (const entry of Object.values(blocks ?? {})) {
    const origin = String(record(entry)?.["origin"] ?? "INCONNUE");
    origins.set(origin, (origins.get(origin) ?? 0) + 1);
  }
  const originText = [...origins.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([origin, n]) => `${ORIGIN_LABELS[origin] ?? origin.toLowerCase()} ${n}`)
    .join(" · ");
  const requests = telemetry["requests_sent"];
  const mode = telemetry["generation_mode"];
  const detail = [
    originText ? `Blocs : ${originText}` : "Provenance par bloc non disponible",
    typeof requests === "number" ? `${plural(requests, "requête")} au modèle` : null,
    typeof mode === "string" ? `mode ${mode}` : null,
  ]
    .filter(Boolean)
    .join(" ; ");
  return { ...base, value: PROVIDER_LABELS[provider] ?? provider, detail, tone: "info" };
}

function globalStatus(doc: DocumentDetail, criticalCount: number): ControlIndicator {
  const base = { key: "status" as const, label: "Statut global du document" };
  const value = statusLabel(doc.status);
  if (doc.status === "APPROVED") {
    return {
      ...base,
      value,
      detail: criticalCount
        ? `Approuvé par un relecteur malgré ${plural(criticalCount, "erreur")} critique(s) détectée(s) automatiquement.`
        : "Validé par un relecteur humain.",
      tone: criticalCount ? "warn" : "ok",
    };
  }
  if (doc.status === "REJECTED" || doc.status === "FAILED") {
    return { ...base, value, detail: "Document non livrable en l’état.", tone: "bad" };
  }
  return {
    ...base,
    value,
    detail: "Aucune validation humaine enregistrée ; une vérification automatique n’en tient pas lieu.",
    tone: doc.status === "REVIEW_REQUIRED" ? "warn" : "unknown",
  };
}

export function controlIndicators(doc: DocumentDetail): ControlIndicator[] {
  const criticalIndicator = critical(doc);
  const criticalCount = criticalIndicator.tone === "bad" ? Number(criticalIndicator.value) : 0;
  return [
    coverage(doc),
    criticalIndicator,
    reconstruction(doc),
    review(doc),
    provenance(doc),
    globalStatus(doc, criticalCount),
  ];
}
