import { Component, inject } from "@angular/core";
import { RouterLink } from "@angular/router";
import { ApiService } from "../core/api.service";
import { Dashboard } from "../core/models";
import { formatMetric } from "../core/formatters";
@Component({
  selector: "ad-dashboard",
  standalone: true,
  imports: [RouterLink],
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">01 / VUE D’ENSEMBLE</p>
        <h1>Le travail en cours.</h1>
        <p class="subtitle">
          Des états lisibles, des décisions traçables. Les chiffres viennent de
          l’API active.
        </p>
      </div>
      <a routerLink="/upload" class="button button-primary"
        >Importer un document <span>＋</span></a
      >
    </section>
    @if (loading) {
      <div class="loading-line">Lecture du tableau de bord…</div>
    } @else if (data) {
      <div class="metric-grid">
        <article class="metric-card">
          <span class="metric-label">Documents suivis</span
          ><strong>{{ data.documents }}</strong
          ><span class="metric-foot">dans ce tenant</span>
        </article>
        <article class="metric-card accent">
          <span class="metric-label">À revoir</span
          ><strong>{{ data.review_required }}</strong
          ><span class="metric-foot">validation humaine</span>
        </article>
        <article class="metric-card">
          <span class="metric-label">Approuvés</span
          ><strong>{{ data.approved }}</strong
          ><span class="metric-foot">versions finales</span>
        </article>
        <article class="metric-card">
          <span class="metric-label">Échecs</span
          ><strong>{{ data.failed }}</strong
          ><span class="metric-foot">à diagnostiquer</span>
        </article>
      </div>
      <div class="dashboard-grid">
        <section class="panel">
          <div class="panel-header">
            <div>
              <p class="eyebrow">ÉTAT DU MOTEUR</p>
              <h2>{{ data.engine || "Non renseigné" }}</h2>
            </div>
            <span class="badge badge-neutral">Endpoint privé</span>
          </div>
          <p class="panel-copy">
            Le moteur déclaré par l’API. Une traduction inconnue reste
            explicitement à vérifier.
          </p>
          <a routerLink="/testing" class="text-link"
            >Voir le rapport d’essais →</a
          >
        </section>
        <section class="panel">
          <div class="panel-header">
            <div>
              <p class="eyebrow">QUALITÉ DOCUMENTAIRE</p>
              <h2>Mesures disponibles</h2>
            </div>
          </div>
          <div class="quality-list">
            <div>
              <span>Géométrie</span
              ><strong>{{ metric(data.metrics.layout_score) }}</strong>
            </div>
            <div>
              <span>OCR</span
              ><strong>{{ metric(data.metrics.ocr_score) }}</strong>
            </div>
            <div>
              <span>Traduction</span
              ><strong>{{ metric(data.metrics.translation_score) }}</strong>
            </div>
            <div>
              <span>Sémantique</span
              ><strong>{{ metric(data.metrics.semantic_score) }}</strong>
            </div>
          </div>
          <p class="muted small">
            Une valeur « Non mesuré » signifie que la preuve nécessaire est
            absente ; elle n’est jamais remplacée par un score par défaut.
          </p>
          @if (data.provenance || data.coverage || data.metrics.provenance || data.metrics.coverage) {
            <div class="quality-evidence">
              <p class="eyebrow">PROVENANCE / COUVERTURE</p>
              @if (data.provenance || data.metrics.provenance) {
                <div><span>Provenance</span><code>{{ evidence(data.provenance || data.metrics.provenance) }}</code></div>
              }
              @if (data.coverage || data.metrics.coverage) {
                <div><span>Couverture mesurée</span><code>{{ evidence(data.coverage || data.metrics.coverage) }}</code></div>
              }
            </div>
          }
        </section>
      </div>
    } @else {
      <div class="empty-state">
        <h2>Tableau indisponible</h2>
        <p>
          Le backend n’a pas retourné de données. Réessayez quand l’API privée
          sera disponible.
        </p>
      </div>
    }`,
  styles: [],
})
export class DashboardPage {
  private readonly api = inject(ApiService);
  data: Dashboard | null = null;
  loading = true;
  readonly metric = formatMetric;
  evidence(value: unknown): string {
    return value == null ? "Non mesuré" : JSON.stringify(value);
  }
  constructor() {
    this.api.dashboard().subscribe({
      next: value => {
        this.data = value;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }
}
