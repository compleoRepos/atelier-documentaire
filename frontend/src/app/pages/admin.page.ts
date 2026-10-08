import { Component, inject } from "@angular/core";
import { ApiService } from "../core/api.service";
import { AdminConfig } from "../core/models";
@Component({
  selector: "ad-admin",
  standalone: true,
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">07 / CONFIGURATION</p>
        <h1>Administration.</h1>
        <p class="subtitle">
          Capacités et configuration non secrète de l’API privée.
        </p>
      </div>
    </section>
    @if (loading) {
      <div class="loading-line">Lecture de la configuration…</div>
    } @else if (config) {
      <section class="panel config-panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">INVENTAIRE PUBLIC AU TENANT ADMIN</p>
            <h2>Configuration active</h2>
          </div>
          <span class="badge badge-approved">Clés masquées</span>
        </div>
        <div class="config-grid">
          @for (item of entries(); track item[0]) {
            <div class="config-item">
              <span>{{ item[0] }}</span
              ><code>{{ display(item[1]) }}</code>
            </div>
          }
        </div>
        <p class="panel-copy">
          Les secrets, tokens et clés ne sont jamais affichés par cette
          interface. Les capacités restent celles réellement renvoyées par
          /api/admin.
        </p>
      </section>
    } @else {
      <div class="empty-state">
        <h2>Configuration indisponible</h2>
        <p>L’API n’a pas retourné de configuration.</p>
      </div>
    }`,
  styles: [],
})
export class AdminPage {
  private readonly api = inject(ApiService);
  config: AdminConfig | null = null;
  loading = true;
  constructor() {
    this.api.admin().subscribe({
      next: v => {
        this.config = v;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }
  entries(): [string, unknown][] {
    return Object.entries(this.config || {});
  }
  display(value: unknown): string {
    const key = JSON.stringify(value);
    return /secret|token|key|password/i.test(key) ? "•••••• (masqué)" : key;
  }
}
