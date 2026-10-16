import { Component, inject } from "@angular/core";
import { Router } from "@angular/router";
import { ApiService } from "../core/api.service";
@Component({
  selector: "ad-upload",
  standalone: true,
  template: `<section class="page-heading">
      <div>
        <p class="eyebrow">03 / INGESTION</p>
        <h1>Importer une pièce.</h1>
        <p class="subtitle">
          L’original reste immuable. L’analyse commence dans le tenant privé
          après contrôle du fichier.
        </p>
      </div>
    </section>
    <div class="upload-layout">
      <section class="panel upload-panel">
        <div class="drop-zone" [class.has-file]="file">
          <div class="upload-symbol">↑</div>
          <h2>{{ file ? file.name : "Choisir un document" }}</h2>
          <p>{{ file ? formatSize(file.size) : "PDF, DOCX, XLSX, PPTX, JPG ou PNG" }}</p>
          <label class="button button-primary"
            >Parcourir les fichiers<input
              type="file"
              accept=".pdf,.docx,.xlsx,.pptx,.jpg,.jpeg,.png,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.openxmlformats-officedocument.presentationml.presentation,image/jpeg,image/png"
              (change)="choose($event)"
              hidden
          /></label>
        </div>
        @if (error) {
          <p class="form-error">{{ error }}</p>
        }
        @if (file) {
          <div class="upload-confirm">
            <span
              ><strong>Contrôle prêt</strong><br /><small
                >Extension autorisée · limite 25 MB</small
              ></span
            ><button
              class="button button-primary"
              [disabled]="busy"
              (click)="send()"
            >
              {{ busy ? "Transmission…" : "Lancer l’analyse" }} →
            </button>
          </div>
        }
      </section>
      <aside class="panel side-note">
        <p class="eyebrow">CONSEILS DE CAPTURE</p>
        <h2>Préparer une revue fiable.</h2>
        <ul>
          <li>
            Préférer un scan net, sans perspective ni compression excessive.
          </li>
          <li>
            Signatures, cachets et manuscrits restent des zones à vérifier.
          </li>
          <li>
            Les fichiers ne sont transmis qu’à l’API configurée par votre
            organisation.
          </li>
        </ul>
        <p class="muted small">
          Taille maximale : 25 MB. Aucun contenu n’est simulé si le moteur est
          indisponible.
        </p>
      </aside>
    </div>`,
  styles: [],
})
export class UploadPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  file: File | null = null;
  error = "";
  busy = false;
  choose(event: Event): void {
    const input = event.target as HTMLInputElement;
    const selected = input.files?.[0];
    this.error = "";
    if (!selected) return;
    const allowed = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "image/jpeg",
      "image/png",
    ];
    if (
      !allowed.includes(selected.type) &&
      !/\.(pdf|docx|xlsx|pptx|jpe?g|png)$/i.test(selected.name)
    ) {
      this.error = "Format refusé. Utilisez PDF, DOCX, XLSX, PPTX, JPG ou PNG.";
      return;
    }
    if (selected.size > 25 * 1024 * 1024) {
      this.error = "Fichier trop volumineux. La limite est de 25 MB.";
      return;
    }
    this.file = selected;
  }
  formatSize(bytes: number): string {
    return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
  }
  send(): void {
    if (!this.file) return;
    this.busy = true;
    this.api.upload(this.file).subscribe({
      next: doc => void this.router.navigate(["/documents", doc.id]),
      error: () => {
        this.busy = false;
        this.error =
          "Import impossible. Le serveur a refusé le fichier ou est indisponible.";
      },
    });
  }
}
