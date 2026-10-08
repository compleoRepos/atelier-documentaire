import { Component, DestroyRef, inject, signal } from "@angular/core";
import {
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
  NavigationEnd,
} from "@angular/router";
import { filter } from "rxjs";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { AuthService } from "./core/auth.service";
import { ErrorService } from "./core/error.service";
@Component({
  selector: "ad-root",
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (isLogin()) {
      <router-outlet />
    } @else {
      <div class="app-shell">
        <aside class="rail" aria-label="Navigation principale">
          <a
            class="brand"
            routerLink="/dashboard"
            aria-label="Accueil Atelier documentaire"
            ><span class="brand-mark">AD</span
            ><span class="brand-name">Atelier<br />documentaire</span></a
          >
          <div class="rail-rule"></div>
          <nav class="nav-stack">
            <a
              routerLink="/dashboard"
              routerLinkActive="active"
              [routerLinkActiveOptions]="{ exact: true }"
              ><span class="nav-index">01</span>Vue d’ensemble</a
            >
            <a routerLink="/documents" routerLinkActive="active"
              ><span class="nav-index">02</span>Documents</a
            >
            <a routerLink="/upload" routerLinkActive="active"
              ><span class="nav-index">03</span>Importer</a
            >
            <a routerLink="/glossary" routerLinkActive="active"
              ><span class="nav-index">04</span>Glossaire</a
            >
            <a routerLink="/translation-memory" routerLinkActive="active"
              ><span class="nav-index">05</span>Mémoire</a
            >
            <a routerLink="/testing" routerLinkActive="active"
              ><span class="nav-index">06</span>Essais</a
            >
            @if (auth.user()?.role === "admin") {
              <a routerLink="/admin" routerLinkActive="active"
                ><span class="nav-index">07</span>Administration</a
              >
            }
            @if (
              auth.user()?.role === "admin" || auth.user()?.role === "reviewer"
            ) {
              <a routerLink="/audit" routerLinkActive="active"
                ><span class="nav-index">08</span>Audit</a
              >
            }
          </nav>
          <div class="rail-footer">
            <span class="live-dot"></span
            ><span>API privée<br /><small>proxy locale /api</small></span>
          </div>
        </aside>
        <main class="workspace">
          <header class="topbar">
            <div>
              <span class="eyebrow"
                >PLATEFORME PRIVÉE / TENANT
                {{ auth.user()?.tenant_id || "—" }}</span
              >
              <div class="topline">Atelier documentaire</div>
            </div>
            <div class="user-menu">
              <span
                >{{ auth.user()?.username || "Session" }} ·
                {{ auth.user()?.role || "rôle non renseigné" }}</span
              ><button
                class="button button-quiet"
                type="button"
                (click)="auth.logout()"
              >
                Se déconnecter
              </button>
            </div>
          </header>
          @if (errors.message()) {
            <div class="global-alert" role="alert">
              <strong>Service indisponible.</strong> {{ errors.message() }}
              <button
                type="button"
                (click)="errors.clear()"
                aria-label="Fermer"
              >
                ×
              </button>
            </div>
          }
          <div class="content"><router-outlet /></div>
        </main>
      </div>
    }
  `,
  styles: [],
})
export class AppComponent {
  readonly auth = inject(AuthService);
  readonly errors = inject(ErrorService);
  readonly isLogin = signal(true);
  private readonly destroyRef = inject(DestroyRef);
  constructor(router: Router) {
    router.events
      .pipe(
        filter(
          (event): event is NavigationEnd => event instanceof NavigationEnd
        ),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe(event =>
        this.isLogin.set(
          event.urlAfterRedirects === "/login" ||
            event.urlAfterRedirects.startsWith("/login?")
        )
      );
    this.isLogin.set(
      router.url === "/login" || router.url.startsWith("/login?")
    );
  }
}
