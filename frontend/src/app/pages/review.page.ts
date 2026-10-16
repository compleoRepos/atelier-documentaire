import { Component, OnDestroy, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { ActivatedRoute, Router, RouterLink } from "@angular/router";
import { Subject, Subscription, forkJoin, of } from "rxjs";
import { catchError, takeUntil } from "rxjs/operators";
import { ApiService } from "../core/api.service";
import {
  Block,
  DocumentDetail,
  ProtectedRegion,
  QualityRubric,
  ReviewPayload,
} from "../core/models";
import {
  buildCorrectionPayload,
  statusClass,
  statusLabel,
} from "../core/formatters";
@Component({
  selector: "ad-review",
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `@if (loading) {
      <div class="loading-line">Chargement des preuves…</div>
    } @else if (doc) {
      <section class="page-heading review-heading">
        <div>
          <a [routerLink]="['/documents', doc.id]" class="back-link"
            >← {{ doc.filename }}</a
          >
          <p class="eyebrow">04 / REVUE HUMAINE / {{ doc.id }}</p>
          <h1>Comparer avant de décider.</h1>
          <p class="subtitle">
            La validation finale appartient au backend après contrôle des
            corrections, des entités et des débordements.
          </p>
          @if (doc.filename.toLowerCase().endsWith(".docx")) {
            <p class="subtitle">
              Word : l’aperçu est logique, pas un rendu de pagination.
              Téléchargez l’original et le candidat depuis la fiche pour
              vérifier leur mise en page.
            </p>
          }
          @if (isOfficeSheetOrSlides(doc.filename)) {
            <p class="subtitle office-native-note">
              Excel / PowerPoint : seuls les textes des cellules et des
              diapositives sont traduits ; la vérification porte sur le fichier
              (formules, noms de feuilles, structure). Aucune preuve visuelle
              n’est mesurée : largeurs de cellules et ajustement du texte sont à
              contrôler en ouvrant le candidat. Commentaires, notes et
              graphiques restent dans la langue d’origine.
            </p>
          }
        </div>
        <span class="badge large" [class]="statusClass(doc.status)">{{
          statusLabel(doc.status)
        }}</span>
      </section>
      <div class="review-toolbar">
        <label
          >Page<select
            [(ngModel)]="selectedPage"
            (ngModelChange)="loadPreviews()"
          >
            @for (page of pages; track page) {
              <option [ngValue]="page">{{ page }}</option>
            }
          </select></label
        ><span class="review-count"
          >{{ blocksForPage().length }} bloc(s) sur cette page</span
        ><span class="review-hint"
          >{{ doc.translation?.untranslated_blocks?.length || 0 }} segment(s)
          non traduit</span
        >
      </div>
      <div class="evidence-grid">
        <figure class="evidence">
          <figcaption><span class="evidence-index">A</span>Original</figcaption>
          @if (images.original) {
            <img [src]="images.original" alt="Aperçu original" />
          } @else {
            <div class="image-missing">Aperçu non disponible</div>
          }
        </figure>
        <figure class="evidence">
          <figcaption><span class="evidence-index amber">B</span>Image prétraitée</figcaption>
          @if (images.enhanced) {
            <img [src]="images.enhanced" alt="Aperçu image prétraitée" />
          } @else {
            <div class="image-missing">Aperçu prétraité non disponible</div>
          }
          <small class="field-help">Confiance OCR : proxy non validé par un humain.</small>
        </figure>
        <figure class="evidence">
          <figcaption>
            <span class="evidence-index petrol">C</span>Traduction candidate
          </figcaption>
          @if (images.translated) {
            <img [src]="images.translated" alt="Aperçu traduit" />
          } @else {
            <div class="image-missing">Aperçu non disponible</div>
          }
        </figure>
        <figure class="evidence">
          <figcaption>
            <span class="evidence-index amber">D</span>Diff
          </figcaption>
          @if (images.diff) {
            <img [src]="images.diff" alt="Différence visuelle" />
          } @else {
            <div class="image-missing">Diff non disponible</div>
          }
        </figure>
      </div>
      <section class="panel correction-panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">BLOCS ÉDITABLES</p>
            <h2>Correction explicite</h2>
          </div>
          <span class="badge badge-neutral">Sauvegarde séparée</span>
        </div>
        @if (blocksForPage().length) {
          <div class="block-list">
            @for (block of blocksForPage(); track block.id) {
              <div class="block-row">
                <div class="block-source">
                  <span class="mono">{{ block.id }}</span>
                  <p>{{ block.text }}</p>
                </div>
                <span class="arrow-muted">→</span
                ><label class="block-edit"
                  ><span>Traduction proposée</span
                  ><textarea
                    rows="2"
                    [ngModel]="correctionFor(block.id)"
                    (ngModelChange)="setCorrection(block.id, $event)"
                  ></textarea>
                </label>
              </div>
            }
          </div>
        } @else {
          <p class="muted">Aucun bloc textuel retourné pour cette page.</p>
        }
      </section>
      <div class="review-lower">
        <section class="panel">
          <p class="eyebrow">PROTECTIONS</p>
          <h2>Entités et zones</h2>
          <label
            >Entités protégées
            <span class="field-help">une ligne par valeur</span
            ><textarea
              rows="4"
              [(ngModel)]="protectedEntitiesText"
              placeholder="N° de contrat&#10;Nom propre à préserver"
            ></textarea></label
          ><label
            >Zones protégées
            <span class="field-help">JSON : page, bbox [x0,y0,x1,y1]</span
            ><textarea
              rows="4"
              [(ngModel)]="protectedRegionsText"
              placeholder='[{"page":1,"bbox":[0,0,100,40]}]'
            ></textarea>
          </label>
        </section>
        <section class="panel decision-panel">
          <p class="eyebrow">DÉCISION</p>
          <h2>Attester la revue</h2>
          <label class="check-row"
            ><input type="checkbox" [(ngModel)]="attestReview" /><span
              >J’ai comparé les preuves et vérifié les blocs édités.</span
            ></label
          ><label
            >Transcription OCR validée (optionnelle)
            <span class="field-help">source relue par l’humain, une ligne par segment si utile</span
            ><textarea
              rows="4"
              [(ngModel)]="ocrText"
              placeholder="Copiez ici la transcription source vérifiée…"
            ></textarea>
          </label>
          <label class="check-row"
            ><input type="checkbox" [(ngModel)]="attestOcr" /><span
              >J’atteste que cette transcription OCR a été comparée à l’original.</span
            ></label
          ><label class="check-row"
            ><input type="checkbox" [(ngModel)]="promoteGolden" /><span
              >Promouvoir cette version en Golden Reference (optionnel).</span
            ></label>
          @if (promoteGolden && doc?.review_version) {
            <div class="rubric-box">
              <p class="eyebrow">RUBRIQUE HUMAINE / 0 À 1</p>
              <p class="field-help">
                Les cinq scores sont obligatoires pour cette version candidate.
                Aucun score n’est prérempli.
              </p>
              <label>Fidélité<input type="number" min="0" max="1" step="0.01" [(ngModel)]="qualityRubricDraft.fidelity" /></label>
              <label>Cohérence<input type="number" min="0" max="1" step="0.01" [(ngModel)]="qualityRubricDraft.coherence" /></label>
              <label>Terminologie<input type="number" min="0" max="1" step="0.01" [(ngModel)]="qualityRubricDraft.terminology" /></label>
              <label>Contexte<input type="number" min="0" max="1" step="0.01" [(ngModel)]="qualityRubricDraft.context" /></label>
              <label>Style<input type="number" min="0" max="1" step="0.01" [(ngModel)]="qualityRubricDraft.style" /></label>
            </div>
          }
          <label
            >Commentaire
            <textarea
              rows="3"
              [(ngModel)]="comment"
              placeholder="Contexte de la décision, ou motif du rejet"
            ></textarea>
          </label>
          @if (message) {
            <p class="form-error">{{ message }}</p>
          }
          <div class="decision-actions">
            <button
              class="button button-secondary"
              [disabled]="saving"
              (click)="submit('correct')"
            >
              Enregistrer les corrections</button
            ><button
              class="button button-danger"
              [disabled]="saving"
              (click)="submit('reject')"
            >
              Rejeter</button
            ><button
              class="button button-primary"
              [disabled]="saving || !attestReview"
              (click)="submit('approve')"
            >
              {{ saving ? "Envoi…" : "Approuver après revue" }} →
            </button>
          </div>
          <p class="muted small">
            Les erreurs critiques, les segments inconnus et les débordements
            restent bloquants. Le backend est l’autorité finale.
          </p>
        </section>
      </div>
    }`,
  styles: [],
})
export class ReviewPage implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  doc: DocumentDetail | null = null;
  loading = true;
  readonly statusClass = statusClass;
  readonly statusLabel = statusLabel;
  /** RUN28: XLSX/PPTX are translated natively, without measured visual proof. */
  isOfficeSheetOrSlides(filename: string): boolean {
    return /\.(xlsx|pptx)$/i.test(filename);
  }
  saving = false;
  selectedPage = 1;
  pages: number[] = [];
  corrections: Record<string, string> = {};
  protectedEntitiesText = "";
  protectedRegionsText = "[]";
  comment = "";
  attestReview = false;
  ocrText = "";
  attestOcr = false;
  promoteGolden = false;
  qualityRubricDraft: Record<keyof QualityRubric, number | null> = {
    fidelity: null,
    coherence: null,
    terminology: null,
    context: null,
    style: null,
  };
  message = "";
  images: {
    original: string | null;
    enhanced: string | null;
    translated: string | null;
    diff: string | null;
  } = { original: null, enhanced: null, translated: null, diff: null };
  private urls: string[] = [];
  private readonly destroyed = new Subject<void>();
  private previewRequest?: Subscription;
  private previewGeneration = 0;
  constructor() {
    const id = this.route.snapshot.paramMap.get("id");
    if (id) this.reloadDocument(id);
  }
  reloadDocument(id: string): void {
    this.loading = true;
    this.api
      .document(id)
      .pipe(takeUntil(this.destroyed))
      .subscribe({
        next: d => {
          this.doc = d;
          const pages = d.analysis?.pages?.map(p => p.number) || [];
          this.pages = pages.length ? pages : [1];
          if (!this.pages.includes(this.selectedPage))
            this.selectedPage = this.pages[0] || 1;
          this.protectedEntitiesText = (d.protected_entities || []).join("\n");
          this.protectedRegionsText = JSON.stringify(
            d.protected_regions || [],
            null,
            2
          );
          this.seedCorrections();
          this.loading = false;
          this.loadPreviews();
        },
        error: () => {
          this.loading = false;
          this.message = "Les preuves n’ont pas pu être rechargées.";
        },
      });
  }
  seedCorrections(): void {
    this.corrections = {};
    for (const block of this.allBlocks())
      this.corrections[block.id] =
        this.doc?.translation?.translations?.[block.id] ?? block.text;
  }
  allBlocks(): Block[] {
    if (!this.doc?.analysis) return [];
    if (this.doc.analysis.blocks) return this.doc.analysis.blocks;
    return (this.doc.analysis.pages || []).flatMap(page => page.blocks || []);
  }
  blocksForPage(): Block[] {
    return this.allBlocks().filter(
      block => block.page === this.selectedPage && block.kind !== "image"
    );
  }
  correctionFor(id: string): string {
    return this.corrections[id] ?? "";
  }
  setCorrection(id: string, value: string): void {
    this.corrections[id] = value;
  }
  loadPreviews(): void {
    if (!this.doc) return;
    this.previewRequest?.unsubscribe();
    this.revokeUrls();
    const generation = ++this.previewGeneration;
    this.previewRequest = forkJoin({
      original: this.api
        .preview(
          this.doc.id,
          "original",
          this.selectedPage,
          this.doc.review_version ?? undefined
        )
        .pipe(catchError(() => of(null))),
      enhanced: this.api
        .preview(
          this.doc.id,
          "enhanced",
          this.selectedPage,
          this.doc.review_version ?? undefined
        )
        .pipe(catchError(() => of(null))),
      translated: this.api
        .preview(
          this.doc.id,
          "translated",
          this.selectedPage,
          this.doc.review_version ?? undefined
        )
        .pipe(catchError(() => of(null))),
      diff: this.api
        .preview(
          this.doc.id,
          "diff",
          this.selectedPage,
          this.doc.review_version ?? undefined
        )
        .pipe(catchError(() => of(null))),
    })
      .pipe(takeUntil(this.destroyed))
      .subscribe(value => {
        if (generation !== this.previewGeneration) return;
        this.images = {
          original: this.toUrl(value.original),
          enhanced: this.toUrl(value.enhanced),
          translated: this.toUrl(value.translated),
          diff: this.toUrl(value.diff),
        };
      });
  }
  toUrl(blob: Blob | null): string | null {
    if (!blob) return null;
    const url = URL.createObjectURL(blob);
    this.urls.push(url);
    return url;
  }
  revokeUrls(): void {
    this.previewGeneration += 1;
    for (const url of this.urls) URL.revokeObjectURL(url);
    this.urls = [];
    this.images = { original: null, enhanced: null, translated: null, diff: null };
  }
  parseRegions(): ProtectedRegion[] | null {
    try {
      const value: unknown = JSON.parse(this.protectedRegionsText);
      if (!Array.isArray(value)) return null;
      return value as ProtectedRegion[];
    } catch {
      return null;
    }
  }
  hasUnsavedChanges(regions: ProtectedRegion[]): boolean {
    const entities = this.protectedEntitiesText
      .split("\n")
      .map(value => value.trim())
      .filter(Boolean);
    return (
      this.allBlocks().some(
        block =>
          this.corrections[block.id] !==
          (this.doc?.translation?.translations?.[block.id] ?? block.text)
      ) ||
      JSON.stringify(entities) !==
        JSON.stringify(this.doc?.protected_entities || []) ||
      JSON.stringify(regions) !==
        JSON.stringify(this.doc?.protected_regions || [])
    );
  }
  humanRubric(): QualityRubric | null {
    const values = Object.values(this.qualityRubricDraft);
    if (
      values.some(
        value =>
          value === null ||
          typeof value !== "number" ||
          !Number.isFinite(value) ||
          value < 0 ||
          value > 1
      )
    )
      return null;
    return { ...this.qualityRubricDraft } as QualityRubric;
  }
  payload(action: "approve" | "reject" | "correct"): ReviewPayload | null {
    const regions = this.parseRegions();
    if (!regions) {
      this.message =
        "Zones protégées : JSON invalide. Utilisez page et bbox [x0,y0,x1,y1].";
      return null;
    }
    if (action === "approve" && !this.attestReview) {
      this.message = "L’attestation de revue est requise pour approuver.";
      return null;
    }
    if (this.ocrText.trim() && !this.attestOcr) {
      this.message =
        "L’attestation OCR est requise lorsque vous fournissez une transcription source.";
      return null;
    }
    if (action === "approve" && this.promoteGolden) {
      if (!this.doc?.review_version) {
        this.message =
          "La promotion Golden exige une version candidate sauvegardée.";
        return null;
      }
      if (!this.humanRubric()) {
        this.message =
          "Renseignez les cinq scores humains entre 0 et 1 avant la promotion Golden.";
        return null;
      }
    }
    if (action === "approve" && this.hasUnsavedChanges(regions)) {
      this.message =
        "Enregistrez les corrections, puis comparez les nouvelles preuves avant d’approuver.";
      return null;
    }
    if (
      action === "correct" &&
      this.allBlocks().some(block => !this.corrections[block.id]?.trim())
    ) {
      this.message =
        "Un bloc source ne peut pas être supprimé par une correction vide.";
      return null;
    }
    if (action === "reject" && !this.comment.trim()) {
      this.message = "Un commentaire est requis pour expliquer un rejet.";
      return null;
    }
    const critical = this.doc?.issues?.some(
      i => i.severity === "critical" || i.severity === "error"
    );
    if (
      action === "approve" &&
      (critical || this.doc?.translation?.untranslated_blocks?.length)
    ) {
      this.message =
        "Approbation bloquée : une erreur critique ou un segment non traduit doit être résolu.";
      return null;
    }
    const rubric =
      action === "approve" && this.promoteGolden
        ? this.humanRubric() || undefined
        : undefined;
    const ocrText = this.ocrText.trim();
    return {
      action,
      corrections: buildCorrectionPayload(this.corrections),
      protected_entities: this.protectedEntitiesText
        .split(String.fromCharCode(10))
        .map(v => v.trim())
        .filter(Boolean),
      protected_regions: regions,
      comment: this.comment.trim(),
      attest_review: this.attestReview,
      promote_golden: action === "approve" && this.promoteGolden,
      expected_version: this.doc?.review_version ?? undefined,
      attest_ocr: this.attestOcr,
      ...(ocrText ? { ocr_text: ocrText } : {}),
      ...(rubric ? { quality_rubric: rubric } : {}),
    };
  }
  submit(action: "approve" | "reject" | "correct"): void {
    this.message = "";
    const id = this.doc?.id;
    const body = id && this.payload(action);
    if (!id || !body) return;
    this.saving = true;
    this.api
      .review(id, body)
      .pipe(takeUntil(this.destroyed))
      .subscribe({
        next: d => {
          this.saving = false;
          this.attestReview = false;
          if (action === "correct") this.reloadDocument(id);
          else {
            this.doc = d;
            void this.router.navigate(["/documents", id]);
          }
        },
        error: () => {
          this.saving = false;
          this.message =
            "La décision n’a pas été acceptée par l’API. Vérifiez les diagnostics et réessayez.";
        },
      });
  }
  ngOnDestroy(): void {
    this.previewRequest?.unsubscribe();
    this.previewGeneration += 1;
    this.destroyed.next();
    this.destroyed.complete();
    this.revokeUrls();
  }
}
