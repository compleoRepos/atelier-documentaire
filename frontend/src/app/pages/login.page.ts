import { Component, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Router, ActivatedRoute } from "@angular/router";
import { AuthService } from "../core/auth.service";
@Component({
  selector: "ad-login",
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <main class="login-layout">
      <section class="login-intro">
        <div class="login-mark">AD</div>
        <p class="eyebrow">PLATEFORME DOCUMENTAIRE PRIVÉE</p>
        <h1>Comprendre,<br /><em>traduire, vérifier.</em></h1>
        <p class="lead">
          Un atelier de travail pour les documents qui demandent des preuves,
          pas des promesses.
        </p>
        <div class="login-note">
          <span class="live-dot"></span
          ><span
            >Endpoint privé uniquement<br /><small
              >Aucun contenu ne quitte votre environnement.</small
            ></span
          >
        </div>
      </section>
      <section class="login-card">
        <p class="eyebrow">ACCÈS ÉQUIPE</p>
        <h2>Ouvrir une session</h2>
        <p class="muted">
          Utilisez un compte provisionné par votre administrateur.
        </p>
        <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
          <label
            >Identifiant<input
              formControlName="username"
              autocomplete="username" /></label
          ><label
            >Mot de passe<input
              type="password"
              formControlName="password"
              autocomplete="current-password"
          /></label>
          @if (error) {
            <p class="form-error" role="alert">{{ error }}</p>
          }
          <button
            class="button button-primary button-wide"
            type="submit"
            [disabled]="form.invalid || busy"
          >
            {{ busy ? "Connexion…" : "Entrer dans l’atelier" }}
            <span aria-hidden="true">→</span>
          </button>
        </form>
        <p class="security-note">
          La session est portée par un cookie HttpOnly privé. Le navigateur
          n’expose aucun JWT à l’interface et protège les écritures par un
          nonce CSRF.
        </p>
      </section>
    </main>
  `,
  styles: [],
})
export class LoginPage {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  readonly form = this.fb.nonNullable.group({
    username: ["", Validators.required],
    password: ["", Validators.required],
  });
  error = "";
  busy = false;
  submit(): void {
    if (this.form.invalid) return;
    this.busy = true;
    this.error = "";
    this.auth
      .login(this.form.getRawValue().username, this.form.getRawValue().password)
      .subscribe({
        next: () => {
          const returnUrl =
            this.route.snapshot.queryParamMap.get("returnUrl") || "/dashboard";
          void this.router.navigateByUrl(returnUrl);
        },
        error: () => {
          this.error =
            "Identifiant ou mot de passe invalide. Aucun détail de sécurité n’est exposé.";
          this.busy = false;
        },
      });
  }
}
