import { Injectable, signal } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Router } from "@angular/router";
import { Observable, of } from "rxjs";
import { catchError, finalize, shareReplay, tap } from "rxjs/operators";
import { AuthResponse, User } from "./models";
@Injectable({ providedIn: "root" })
export class AuthService {
  private readonly tokenKey = "atelier_access_token";
  private readonly userKey = "atelier_user";
  readonly user = signal<User | null>(null);
  readonly initialized = signal(false);
  private restoreRequest?: Observable<User | null>;
  constructor(
    private readonly http: HttpClient,
    private readonly router: Router
  ) {
    this.clearLegacyStoredToken();
  }
  get token(): string | null {
    // Kept only as a compatibility seam for old callers. Browser code never
    // reads or stores an access token; authentication is cookie based.
    return null;
  }
  login(username: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>("/api/auth/login", { username, password }, {
        withCredentials: true,
      })
      .pipe(tap(response => this.setUser(response.user)));
  }
  restore(): Observable<User | null> {
    if (!this.restoreRequest) {
      this.restoreRequest = this.http
        .get<User>("/api/auth/me", { withCredentials: true })
        .pipe(
          tap(value => this.setUser(value)),
          catchError(() => {
            this.user.set(null);
            return of(null);
          }),
          finalize(() => this.initialized.set(true)),
          shareReplay({ bufferSize: 1, refCount: false })
        );
    }
    return this.restoreRequest;
  }
  logout(redirect = true): void {
    this.http
      .post("/api/auth/logout", {}, { withCredentials: true })
      .pipe(
        catchError(() => of(null)),
        finalize(() => {
          this.clearSession();
          this.initialized.set(true);
          if (redirect) void this.router.navigate(["/login"]);
        })
      )
      .subscribe();
  }
  hasRole(roles: string[]): boolean {
    const role = this.user()?.role;
    return role !== undefined && roles.includes(role);
  }
  private setUser(value: User): void {
    this.user.set(value);
    this.initialized.set(true);
  }
  private clearSession(): void {
    this.user.set(null);
    this.clearLegacyStoredToken();
  }
  clearLegacyStoredToken(): void {
    if (typeof sessionStorage !== "undefined") {
      sessionStorage.removeItem(this.tokenKey);
      sessionStorage.removeItem(this.userKey);
    }
  }
}
