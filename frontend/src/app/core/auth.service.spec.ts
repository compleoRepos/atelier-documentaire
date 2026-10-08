import { provideHttpClient } from "@angular/common/http";
import {
  HttpTestingController,
  provideHttpClientTesting,
} from "@angular/common/http/testing";
import { TestBed } from "@angular/core/testing";
import { Router } from "@angular/router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthService } from "./auth.service";
import { User } from "./models";

const user: User = {
  id: "user-1",
  username: "reviewer",
  tenant_id: "tenant-1",
  role: "reviewer",
};

describe("AuthService cookie session", () => {
  let auth: AuthService;
  let http: HttpTestingController;

  beforeEach(() => {
    sessionStorage.setItem("atelier_access_token", "legacy-jwt");
    sessionStorage.setItem("atelier_user", JSON.stringify({ ...user, role: "admin" }));
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: Router, useValue: { navigate: vi.fn() } },
      ],
    });
    auth = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it("clears legacy JWT and cached role data on initialization", () => {
    expect(sessionStorage.getItem("atelier_access_token")).toBeNull();
    expect(sessionStorage.getItem("atelier_user")).toBeNull();
    expect(auth.user()).toBeNull();
  });

  it("restores the authoritative user from /auth/me without storing a JWT", () => {
    let restored: User | null | undefined;
    auth.restore().subscribe(value => (restored = value));
    const request = http.expectOne("/api/auth/me");
    expect(request.request.withCredentials).toBe(true);
    request.flush(user);
    expect(restored).toEqual(user);
    expect(auth.user()).toEqual(user);
    expect(auth.initialized()).toBe(true);
    expect(sessionStorage.getItem("atelier_access_token")).toBeNull();
    expect(sessionStorage.getItem("atelier_user")).toBeNull();
  });
});
