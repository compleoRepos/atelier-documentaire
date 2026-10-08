import { HttpRequest, HttpResponse } from "@angular/common/http";
import { describe, expect, it, vi } from "vitest";
import { of } from "rxjs";
import { authInterceptor } from "./auth.interceptor";

describe("authInterceptor", () => {
  it("sends the readable CSRF nonce with cookie-authenticated mutations", () => {
    Object.defineProperty(document, "cookie", {
      configurable: true,
      value: "translator_csrf=nonce-123",
    });
    const captured: { request?: HttpRequest<unknown> } = {};
    const next = (value: HttpRequest<unknown>) => {
      captured.request = value;
      return of(new HttpResponse({ status: 200 }));
    };
    const request = new HttpRequest("POST", "/api/documents", {});

    authInterceptor(request, next).subscribe();

    expect(captured.request?.withCredentials).toBe(true);
    expect(captured.request?.headers.get("X-CSRF-Token")).toBe("nonce-123");
  });
});
