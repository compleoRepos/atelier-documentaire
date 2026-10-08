import { Component, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { ApiService } from "../core/api.service";
import { AuditEvent } from "../core/models";
@Component({
  selector: "ad-audit",
  standalone: true,
  imports: [CommonModule],
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">08 / TRAÇABILITÉ</p>
        <h1>Journal d’audit</h1>
        <p class="subtitle">
          Événements du tenant, sans texte de document ni secret.
        </p>
      </div>
    </section>
    <section class="panel table-panel">
      @if (loading) {
        <div class="loading-line">Lecture du journal…</div>
      } @else if (events.length) {
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Horodatage</th>
                <th>Action</th>
                <th>Document</th>
                <th>Utilisateur</th>
                <th>Détails sûrs</th>
              </tr>
            </thead>
            <tbody>
              @for (event of events; track event.id) {
                <tr>
                  <td>{{ event.timestamp | date: "dd/MM/yyyy HH:mm:ss" }}</td>
                  <td>
                    <span class="badge badge-neutral">{{ event.action }}</span>
                  </td>
                  <td class="mono">{{ event.document_id || "—" }}</td>
                  <td class="mono">{{ event.user_id || "—" }}</td>
                  <td>
                    <code>{{ safeDetails(event.details) }}</code>
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      } @else {
        <div class="empty-state">
          <h2>Journal vide</h2>
          <p>Aucun événement n’a été retourné par l’API.</p>
        </div>
      }
    </section>`,
  styles: [],
})
export class AuditPage {
  private readonly api = inject(ApiService);
  events: AuditEvent[] = [];
  loading = true;
  constructor() {
    this.api.audit().subscribe({
      next: v => {
        this.events = v;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }
  safeDetails(details: unknown): string {
    try {
      return JSON.stringify(details ?? {});
    } catch {
      return "[détails non sérialisables]";
    }
  }
}
