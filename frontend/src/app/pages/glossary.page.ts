import { Component, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { ApiService } from "../core/api.service";
import { GlossaryEntry } from "../core/models";
@Component({
  selector: "ad-glossary",
  standalone: true,
  imports: [FormsModule],
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">04 / CONTEXTE CONTRÔLÉ</p>
        <h1>Glossaire</h1>
        <p class="subtitle">
          Les termes validés cadrent la traduction sans masquer les segments
          inconnus.
        </p>
      </div>
    </section>
    <div class="two-col">
      <section class="panel">
        <div class="panel-header">
          <div>
            <p class="eyebrow">TERMINOLOGIE DU TENANT</p>
            <h2>{{ entries.length }} terme(s)</h2>
          </div>
        </div>
        @if (loading) {
          <div class="loading-line">Lecture du glossaire…</div>
        } @else if (entries.length) {
          <div class="term-list">
            @for (entry of entries; track entry.id) {
              <div class="term-row">
                <div>
                  <strong>{{ entry.source }}</strong
                  ><span>{{ entry.domain || "Domaine non renseigné" }}</span>
                </div>
                <span class="term-arrow">→</span>
                <div>
                  <strong>{{ entry.target }}</strong
                  ><span>version {{ entry.version ?? "—" }}</span>
                </div>
              </div>
            }
          </div>
        } @else {
          <p class="muted">Aucun terme validé dans ce tenant.</p>
        }
      </section>
      <section class="panel form-panel">
        <p class="eyebrow">AJOUTER UN TERME</p>
        <h2>Nouvelle entrée</h2>
        <label
          >Source<input
            [(ngModel)]="source"
            placeholder="Terme source" /></label
        ><label
          >Cible<input
            [(ngModel)]="target"
            placeholder="Traduction validée" /></label
        ><label
          >Domaine<input [(ngModel)]="domain" placeholder="ex. juridique"
        /></label>
        @if (message) {
          <p class="form-error">{{ message }}</p>
        }
        <button class="button button-primary" [disabled]="busy" (click)="add()">
          {{ busy ? "Enregistrement…" : "Ajouter au glossaire" }} →
        </button>
        <p class="muted small">
          L’API reste autoritaire sur le rôle et la version.
        </p>
      </section>
    </div>`,
  styles: [],
})
export class GlossaryPage {
  private readonly api = inject(ApiService);
  entries: GlossaryEntry[] = [];
  loading = true;
  busy = false;
  source = "";
  target = "";
  domain = "";
  message = "";
  constructor() {
    this.load();
  }
  load(): void {
    this.api.glossary().subscribe({
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
    this.message = "";
    this.api
      .addGlossary({
        source: this.source.trim(),
        target: this.target.trim(),
        domain: this.domain.trim(),
      })
      .subscribe({
        next: v => {
          this.entries = [...this.entries, v];
          this.source = "";
          this.target = "";
          this.domain = "";
          this.busy = false;
        },
        error: () => {
          this.busy = false;
          this.message = "Ajout refusé par l’API.";
        },
      });
  }
}
