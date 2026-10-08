import { DocumentStatus } from "./models";
export function formatMetric(value: number | null | undefined): string {
  return value === null || value === undefined
    ? "Non mesuré"
    : `${Math.round(value * 100)} %`;
}
export function statusLabel(status: DocumentStatus): string {
  const labels: Record<string, string> = {
    UPLOADED: "Importé",
    ANALYZING: "Analyse en cours",
    ANALYZED: "Analysé",
    TRANSLATING: "Traduction en cours",
    REVIEW_REQUIRED: "Revue requise",
    APPROVED: "Approuvé",
    REJECTED: "Rejeté",
    FAILED: "Échec",
  };
  return labels[status] ?? status;
}
export function statusClass(status: DocumentStatus): string {
  return `status-${status.toLowerCase().replaceAll("_", "-")}`;
}
export function isJobActive(status: DocumentStatus): boolean {
  return status === "ANALYZING" || status === "TRANSLATING";
}

export function buildCorrectionPayload(
  corrections: Record<string, string>
): Record<string, string> {
  return Object.fromEntries(
    Object.entries(corrections).filter(([, text]) => text.trim().length > 0)
  );
}
