import { Component, inject } from "@angular/core";
import { ApiService } from "../core/api.service";
import { TestingReport } from "../core/models";
import { formatMetric } from "../core/formatters";
@Component({
  selector: "ad-testing",
  standalone: true,
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">06 / PREUVES D’EXÉCUTION</p>
        <h1>Essais du corpus.</h1>
        <p class="subtitle">
          Un rapport réel, fourni par l’API. Les valeurs absentes restent non
          mesurées.
        </p>
      </div>
    </section>
    @if (loading) {
      <div class="loading-line">Lecture du rapport…</div>
    } @else if (data) {
      <div class="metric-grid">
        <article class="metric-card">
          <span class="metric-label">Documents testés</span
          ><strong>{{ data.documents ?? "Non mesuré" }}</strong
          ><span class="metric-foot"
            >corpus disponible :
            {{ data.dataset_available ? "oui" : "non" }}</span
          >
        </article>
        <article class="metric-card">
          <span class="metric-label">Tests passés</span
          ><strong>{{ data.tests_passed ?? "Non mesuré" }}</strong
          ><span class="metric-foot">retour API</span>
        </article>
        <article class="metric-card">
          <span class="metric-label">Tests en échec</span
          ><strong>{{ data.tests_failed ?? "Non mesuré" }}</strong
          ><span class="metric-foot">retour API</span>
        </article>
      </div>
      <section class="panel report-panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">RÉFÉRENCE GOLDEN</p>
            <h2>{{ data.reference_status || "Statut non renseigné" }}</h2>
          </div>
          <span class="badge badge-amber">Aucune métrique inventée</span>
        </div>
        <div class="quality-list">
          <div>
            <span>OCR</span
            ><strong>{{ metric(data.metrics?.ocr_score) }}</strong>
          </div>
          <div>
            <span>Traduction</span
            ><strong>{{ metric(data.metrics?.translation_score) }}</strong>
          </div>
          <div>
            <span>Sémantique</span
            ><strong>{{ metric(data.metrics?.semantic_score) }}</strong>
          </div>
          <div>
            <span>Visuel</span
            ><strong>{{ metric(data.metrics?.visual_score) }}</strong>
          </div>
        </div>
        <p class="panel-copy">
          Sans référence validée par une revue humaine, la qualité linguistique
          reste non mesurée. Ce panneau ne fabrique aucun pourcentage.
        </p>
      </section>
    } @else {
      <div class="empty-state">
        <h2>Rapport indisponible</h2>
        <p>Le endpoint /api/testing n’a pas répondu.</p>
      </div>
    }`,
  styles: [],
})
export class TestingPage {
  private readonly api = inject(ApiService);
  data: TestingReport | null = null;
  loading = true;
  readonly metric = formatMetric;
  constructor() {
    this.api.testing().subscribe({
      next: v => {
        this.data = v;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }
}
