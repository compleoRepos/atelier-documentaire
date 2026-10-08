import { Component, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ApiService } from "../core/api.service";
import { MemoryEntry } from "../core/models";
@Component({
  selector: "ad-memory",
  standalone: true,
  imports: [FormsModule],
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">05 / CONTEXTE CONTRÔLÉ</p>
        <h1>Mémoire de traduction</h1>
        <p class="subtitle">
          Uniquement les décisions explicitement validées par un relecteur.
        </p>
      </div>
    </section>
    <div class="two-col">
      <section class="panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">SEGMENTS VALIDÉS</p>
            <h2>{{ entries.length }} entrée(s)</h2>
          </div>
        </div>
        @if (loading) {
          <div class="loading-line">Lecture de la mémoire…</div>
        } @else if (entries.length) {
          <div class="term-list">
            @for (entry of entries; track entry.id) {
              <div class="term-row">
                <div>
                  <strong>{{ entry.source }}</strong
                  ><span class="mono">{{ entry.id }}</span>
                </div>
                <span class="term-arrow">→</span>
                <div>
                  <strong>{{ entry.target }}</strong
                  ><span
                    ><span class="badge badge-approved">Validé</span> · v{{
                      entry.version ?? "—"
                    }}</span
                  >
                </div>
              </div>
            }
          </div>
        } @else {
          <p class="muted">Aucune mémoire validée.</p>
        }
      </section>
      <section class="panel form-panel">
        <p class="eyebrow">PROPOSER UNE ENTRÉE</p>
        <h2>Ajouter après contrôle</h2>
        <label>Source<input [(ngModel)]="source" /></label
        ><label>Cible<input [(ngModel)]="target" /></label>
        @if (message) {
          <p class="form-error">{{ message }}</p>
        }
        <button class="button button-primary" [disabled]="busy" (click)="add()">
          {{ busy ? "Enregistrement…" : "Soumettre la paire" }} →
        </button>
        <p class="muted small">
          La validation humaine et les droits reviewer sont contrôlés par le
          backend.
        </p>
      </section>
    </div>`,
  styles: [],
})
export class MemoryPage {
  private readonly api = inject(ApiService);
  entries: MemoryEntry[] = [];
  loading = true;
  busy = false;
  source = "";
  target = "";
  message = "";
  constructor() {
    this.load();
  }
  load(): void {
    this.api.memory().subscribe({
      next: v => {
        this.entries = v;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }
  add(): void {
    if (!this.source.trim() || !this.target.trim()) {
      this.message = "Source et cible sont obligatoires.";
      return;
    }
    this.busy = true;
    this.api
      .addMemory({ source: this.source.trim(), target: this.target.trim() })
      .subscribe({
        next: v => {
          this.entries = [...this.entries, v];
          this.source = "";
          this.target = "";
          this.busy = false;
        },
        error: () => {
          this.busy = false;
          this.message =
            "Ajout refusé : un rôle reviewer est requis ou l’API est indisponible.";
        },
      });
  }
}
