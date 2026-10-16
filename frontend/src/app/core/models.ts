export type Role = "admin" | "reviewer" | "operator" | "viewer" | string;
export type DocumentStatus =
  | "UPLOADED"
  | "ANALYZING"
  | "ANALYZED"
  | "TRANSLATING"
  | "REVIEW_REQUIRED"
  | "APPROVED"
  | "REJECTED"
  | "FAILED"
  | string;
export interface User {
  id: string;
  username: string;
  tenant_id: string;
  role: Role;
}
export interface AuthResponse {
  access_token?: string;
  token_type: string;
  user: User;
}
export interface Issue {
  code: string;
  severity: "critical" | "error" | "warning" | "info" | string;
  message: string;
  block_id?: string | null;
}
export interface DashboardMetrics {
  layout_score: number | null;
  visual_score: number | null;
  ocr_score: number | null;
  translation_score: number | null;
  semantic_score: number | null;
  provenance?: QualityEvidence | null;
  coverage?: QualityEvidence | null;
  [key: string]: number | QualityEvidence | null | undefined;
}
export interface QualityEvidence {
  [key: string]: unknown;
}
export interface Dashboard {
  documents: number;
  review_required: number;
  approved: number;
  failed: number;
  engine: string;
  metrics: DashboardMetrics;
  provenance?: QualityEvidence | null;
  coverage?: QualityEvidence | null;
}
export interface Block {
  id: string;
  page: number;
  kind: string;
  text: string;
  bbox?: number[];
  confidence?: number | null;
  language?: string | null;
}
export interface Analysis {
  pages?: Array<{
    number: number;
    width: number;
    height: number;
    scanned?: boolean;
    blocks?: Block[];
    preprocessing?: PagePreprocessing;
    processing_image_path?: string | null;
    protected_visual_regions?: ProtectedVisualRegion[];
  }>;
  blocks?: Block[];
  warnings?: string[];
  [key: string]: unknown;
}
export interface OCRSnapshot {
  confidence: number | null;
  characters: number;
  blocks: number;
  model: string | null;
  version: string | null;
  languages: string[];
}
export interface PagePreprocessing {
  version: string;
  profile: string;
  selected_variant: string;
  operations: Array<Record<string, unknown> | string>;
  transform_source_to_processing: number[][];
  transform_processing_to_source: number[][];
  source_size: [number, number] | number[];
  processing_size: [number, number] | number[];
  ocr_before: OCRSnapshot;
  ocr_after: OCRSnapshot;
  quality?: PreprocessingQualityScore;
  quality_score?: PreprocessingQualityScore;
  PreprocessingQualityScore?: PreprocessingQualityScore;
}
export interface PreprocessingQualityScore {
  confidence_before: number | null;
  confidence_after: number | null;
  improvement: number | null;
  metric: "ocr_confidence_proxy";
  cer: null;
  wer: null;
  validated: false;
}
export interface ProtectedVisualRegion {
  type: "protected_visual_region";
  subtype: string;
  page: number;
  bbox: [number, number, number, number];
  authenticated: boolean;
  candidate: boolean;
}
export interface Translation {
  translations: Record<string, string>;
  issues: Issue[];
  untranslated_blocks: string[];
  [key: string]: unknown;
}
export interface DocumentSummary {
  id: string;
  filename: string;
  status: DocumentStatus;
  created_at: string;
  language?: string | null;
  document_type?: string | null;
  domain?: string | null;
  page_count?: number | null;
  quality?: DashboardMetrics | null;
  review_version?: number | null;
  stages?: DocumentStage[];
}
export interface DocumentStage {
  id: string;
  label: string;
  state: "pending" | "running" | "completed" | "failed" | string;
  evidence?: string;
}
export interface DocumentDetail extends DocumentSummary {
  issues: Issue[];
  analysis?: Analysis | null;
  translation?: Translation | null;
  protected_entities?: string[];
  protected_regions?: ProtectedRegion[];
  timings?: Record<string, number | null> | null;
  source_sha256?: string | null;
  analysis_revision?: number | null;
  provider_requested?: "offline" | "private" | "interim";
  model_requested?: string | null;
  interim_notice?: string | null;
  quality_provenance?: QualityEvidence | null;
  quality_coverage?: QualityEvidence | null;
}
export interface GlossaryEntry {
  id: string;
  source: string;
  target: string;
  domain?: string | null;
  version?: number | null;
}
export interface MemoryEntry {
  id: string;
  source: string;
  target: string;
  validated: boolean;
  version?: number | null;
}
export interface AuditEvent {
  id: string;
  action: string;
  document_id?: string | null;
  user_id?: string | null;
  timestamp: string;
  details?: unknown;
}
export interface TestingReport {
  dataset_available: boolean;
  documents: number | null;
  tests_passed: number | null;
  tests_failed: number | null;
  metrics: DashboardMetrics | null;
  reference_status: string | null;
}
export interface AdminConfig {
  [key: string]: unknown;
}
export interface ProtectedRegion {
  page: number;
  bbox: [number, number, number, number];
  type?: "protected_visual_region";
  subtype?: string;
  authenticated?: boolean;
  candidate?: boolean;
}
export interface ReviewPayload {
  action: "approve" | "reject" | "correct";
  corrections: Record<string, string>;
  protected_entities: string[];
  protected_regions: ProtectedRegion[];
  comment: string;
  attest_review: boolean;
  promote_golden: boolean;
  expected_version?: number;
  ocr_text?: string;
  attest_ocr: boolean;
  quality_rubric?: QualityRubric;
}
export interface QualityRubric {
  fidelity: number;
  coherence: number;
  terminology: number;
  context: number;
  style: number;
}
