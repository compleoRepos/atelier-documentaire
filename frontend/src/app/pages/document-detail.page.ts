import { Component, DestroyRef, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ActivatedRoute, RouterLink } from "@angular/router";
import { timer, switchMap, take, takeWhile } from "rxjs";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { ApiService } from "../core/api.service";
import { DocumentDetail } from "../core/models";
import {
  isJobActive,
  statusClass,
  statusLabel,
  formatMetric,
} from "../core/formatters";
@Component({
  selector: "ad-document-detail",
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `@if (loading) {
      <div class="loading-line">Lecture du document…</div>
    } @else if (doc) {
      <section class="page-heading">
        <div>
          <a routerLink="/documents" class="back-link">← Corpus</a>
          <p class="eyebrow">DOCUMENT / {{ doc.id }}</p>
          <h1>{{ doc.filename }}</h1>
          <p class="subtitle">
            {{ doc.document_type || "Type non renseigné" }} ·
            {{ doc.domain || "Domaine non renseigné" }} ·
            {{ doc.page_count ?? "—" }} page(s)
          </p>
        </div>
        <span class="badge large" [class]="statusClass(doc.status)">{{
          statusLabel(doc.status)
        }}</span>
      </section>
      <div class="sequence">
        <div class="sequence-step" [class.done]="stageAtLeast(1)">
          <span>01</span><b>Importer</b><small>Original immuable</small>
        </div>
        <div class="sequence-step" [class.done]="stageAtLeast(2)">
          <span>02</span><b>Analyser</b><small>Structure et OCR</small>
        </div>
        <div class="sequence-step" [class.done]="stageAtLeast(3)">
          <span>03</span><b>Traduire</b><small>Moteur privé / hors ligne</small>
        </div>
        <div class="sequence-step" [class.done]="stageAtLeast(4)">
          <span>04</span><b>Vérifier</b><small>Décision humaine</small>
        </div>
      </div>
      <div class="detail-grid">
        <section class="panel">
          <div class="panel-header">
            <div>
              <p class="eyebrow">COMMANDES API</p>
              <h2>Faire avancer le document</h2>
            </div>
          </div>
          <div class="command-list">
            <button
              class="command"
              [disabled]="busy || !canAnalyze()"
              (click)="runAnalyze()"
            >
              <span class="command-number">A</span
              ><span
                ><strong>Analyser la structure</strong
                ><small>POST /documents/{{ doc.id }}/analyze</small></span
              ><span>→</span></button
            ><button
              class="command"
              [disabled]="busy || !canTranslate()"
              (click)="runTranslate()"
            >
              <span class="command-number">T</span
              ><span
                ><strong>Lancer la traduction</strong
                ><small>POST /documents/{{ doc.id }}/translate</small></span
              ><span>→</span></button
            ><a
              class="command"
              [class.disabled-link]="doc.status !== 'REVIEW_REQUIRED'"
              [routerLink]="
                doc.status === 'REVIEW_REQUIRED' ? ['/review', doc.id] : null
              "
              ><span class="command-number">R</span
              ><span
                ><strong>Ouvrir la revue</strong
                ><small>Correction, preuve et décision</small></span
              ><span>→</span></a
            >
          </div>
          @if (busy) {
            <p class="inline-note">
              Job en cours. L’état est rafraîchi pendant au plus 25 secondes.
            </p>
          }
          @if (doc.status === "FAILED") {
            <div class="failure-box">
              <strong>Échec terminal.</strong>
              <p>
                Le backend a signalé un échec. Vérifiez les problèmes ci-dessous
                avant de relancer une commande.
              </p>
              <button class="button button-secondary" (click)="reload()">
                Réessayer la lecture
              </button>
            </div>
          }
        </section>
        <section class="panel">
          <div class="panel-header">
            <div>
              <p class="eyebrow">PREUVES RETOURNÉES</p>
              <h2>État de qualité</h2>
            </div>
          </div>
          <div class="quality-list">
            <div>
              <span>Géométrie</span
              ><strong>{{ metric(doc.quality?.layout_score) }}</strong>
            </div>
            <div>
              <span>OCR</span
              ><strong>{{ metric(doc.quality?.ocr_score) }}</strong>
            </div>
            <div>
              <span>Traduction</span
              ><strong>{{ metric(doc.quality?.translation_score) }}</strong>
            </div>
            <div>
              <span>Sémantique</span
              ><strong>{{ metric(doc.quality?.semantic_score) }}</strong>
            </div>
          </div>
          <dl class="evidence-meta">
            <div><dt>Révision analyse</dt><dd>{{ doc.analysis_revision ?? "Non mesurée" }}</dd></div>
            <div><dt>Empreinte source</dt><dd class="mono">{{ doc.source_sha256 || "Non renseignée" }}</dd></div>
            <div><dt>Timings mesurés</dt><dd>{{ timingSummary(doc.timings) }}</dd></div>
          </dl>
          @if (doc.quality?.provenance || doc.quality?.coverage) {
            <div class="quality-evidence">
              <p class="eyebrow">PROVENANCE / COUVERTURE</p>
              @if (doc.quality?.provenance) {
                <div><span>Provenance</span><code>{{ evidence(doc.quality?.provenance) }}</code></div>
              }
              @if (doc.quality?.coverage) {
                <div><span>Couverture mesurée</span><code>{{ evidence(doc.quality?.coverage) }}</code></div>
              }
            </div>
          }
        </section>
      </div>
      <section class="panel issue-panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">ISSUES / DIAGNOSTICS</p>
            <h2>{{ doc.issues.length || 0 }} signalement(s)</h2>
          </div>
        </div>
        @if (doc.issues.length) {
          <ul class="issue-list">
            @for (issue of doc.issues; track $index) {
              <li>
                <span class="severity" [class]="'severity-' + issue.severity">{{
                  issue.severity
                }}</span
                ><span>{{ issue.message }}</span>
                @if (issue.block_id) {
                  <code>{{ issue.block_id }}</code>
                }
              </li>
            }
          </ul>
        } @else {
          <p class="muted">Aucun signalement retourné par l’API.</p>
        }
      </section>
    }`,
  styles: [],
})
export class DocumentDetailPage {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  doc: DocumentDetail | null = null;
  loading = true;
  busy = false;
  readonly metric = formatMetric;
  readonly statusClass = statusClass;
  readonly statusLabel = statusLabel;
  evidence(value: unknown): string {
    return value == null ? "Non mesuré" : JSON.stringify(value);
  }
  timingSummary(timings: Record<string, number | null> | null | undefined): string {
    if (!timings) return "Non mesuré";
    const measured = Object.entries(timings).filter(
      ([, value]) => typeof value === "number" && Number.isFinite(value)
    );
    return measured.length
      ? measured.map(([key, value]) => `${key}: ${value} ms`).join(" · ")
      : "Non mesuré";
  }
  constructor() {
    this.reload();
  }
  reload(): void {
    const id = this.route.snapshot.paramMap.get("id");
    if (!id) return;
    this.loading = true;
    this.api.document(id).subscribe({
      next: d => {
        this.doc = d;
        this.loading = false;
        this.startPolling(id);
      },
      error: () => (this.loading = false),
    });
  }
  startPolling(id: string): void {
    if (!this.doc || !isJobActive(this.doc.status)) return;
    this.busy = true;
    timer(2500, 2500)
      .pipe(
        take(10),
        switchMap(() => this.api.document(id)),
        takeWhile(d => isJobActive(d.status), true),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe({
        next: d => {
          this.doc = d;
          if (!isJobActive(d.status)) this.busy = false;
        },
        error: () => (this.busy = false),
        complete: () => (this.busy = false),
      });
  }
  runAnalyze(): void {
    if (!this.doc) return;
    this.busy = true;
    this.api.analyze(this.doc.id).subscribe({
      next: d => {
        this.doc = d;
        this.startPolling(d.id);
      },
      error: () => (this.busy = false),
    });
  }
  runTranslate(): void {
    if (!this.doc) return;
    this.busy = true;
    this.api.translate(this.doc.id).subscribe({
      next: d => {
        this.doc = d;
        this.startPolling(d.id);
      },
      error: () => (this.busy = false),
    });
  }
  canAnalyze(): boolean {
    return (
      !!this.doc &&
      (this.doc.status === "UPLOADED" || this.doc.status === "FAILED")
    );
  }
  canTranslate(): boolean {
    return (
      !!this.doc &&
      (this.doc.status === "ANALYZED" || this.doc.status === "FAILED")
    );
  }
  stageAtLeast(stage: number): boolean {
    const status = this.doc?.status;
    return (
      stage === 1 ||
      (stage === 2 &&
        [
          "ANALYZED",
          "TRANSLATING",
          "REVIEW_REQUIRED",
          "APPROVED",
          "REJECTED",
        ].includes(status || "")) ||
      (stage === 3 &&
        ["REVIEW_REQUIRED", "APPROVED", "REJECTED"].includes(status || "")) ||
      (stage === 4 && ["APPROVED", "REJECTED"].includes(status || ""))
    );
  }
}
