import { Component, inject } from "@angular/core";
import { CommonModule } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { RouterLink } from "@angular/router";
import { ApiService } from "../core/api.service";
import { DocumentSummary } from "../core/models";
import { statusClass, statusLabel } from "../core/formatters";
@Component({
  selector: "ad-documents",
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">02 / CORPUS</p>
        <h1>Documents</h1>
        <p class="subtitle">
          Chaque fichier conserve son origine, ses versions et la décision
          humaine.
        </p>
      </div>
      <a routerLink="/upload" class="button button-primary"
        >Importer <span>＋</span></a
      >
    </section>
    <section class="panel table-panel">
      <div class="toolbar">
        <label class="search-field"
          ><span aria-hidden="true">⌕</span
          ><input
            [(ngModel)]="query"
            placeholder="Rechercher un nom, domaine ou statut"
            aria-label="Rechercher" /></label
        ><span class="result-count">{{ filtered().length }} résultat(s)</span>
      </div>
      @if (loading) {
        <div class="loading-line">Lecture du corpus…</div>
      } @else if (filtered().length) {
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Document</th>
                <th>État</th>
                <th>Langues / domaine</th>
                <th>Pages</th>
                <th>Date</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              @for (doc of filtered(); track doc.id) {
                <tr>
                  <td>
                    <a
                      class="document-link"
                      [routerLink]="['/documents', doc.id]"
                      >{{ doc.filename }}</a
                    ><span class="mono">{{ doc.id }}</span>
                  </td>
                  <td>
                    <span class="badge" [class]="statusClass(doc.status)">{{
                      statusLabel(doc.status)
                    }}</span>
                  </td>
                  <td>
                    {{ doc.language || "—" }}
                    <span class="muted"
                      >/ {{ doc.domain || "Domaine non renseigné" }}</span
                    >
                  </td>
                  <td>{{ doc.page_count ?? "—" }}</td>
                  <td>{{ doc.created_at | date: "dd/MM/yyyy HH:mm" }}</td>
                  <td>
                    <a
                      [routerLink]="['/documents', doc.id]"
                      class="arrow-link"
                      aria-label="Ouvrir"
                      >→</a
                    >
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
      } @else {
        <div class="empty-state">
          <h2>{{ query ? "Aucun résultat" : "Aucun document" }}</h2>
          <p>
            {{
              query
                ? "Modifiez le filtre ou vérifiez l’orthographe."
                : "Importez un premier document pour lancer l’analyse locale."
            }}
          </p>
        </div>
      }
    </section>`,
  styles: [],
})
export class DocumentsPage {
  private readonly api = inject(ApiService);
  documents: DocumentSummary[] = [];
  query = "";
  loading = true;
  readonly statusClass = statusClass;
  readonly statusLabel = statusLabel;
  constructor() {
    this.api.documents().subscribe({
      next: v => {
        this.documents = v;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }
  filtered(): DocumentSummary[] {
    const q = this.query.trim().toLocaleLowerCase();
    return this.documents.filter(
      d =>
        !q ||
        [d.filename, d.status, d.domain || "", d.language || ""].some(v =>
          v.toLocaleLowerCase().includes(q)
        )
    );
  }
}
