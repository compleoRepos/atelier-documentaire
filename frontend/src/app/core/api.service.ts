import { Injectable } from "@angular/core";
import { HttpClient, HttpHeaders, HttpParams } from "@angular/common/http";
import { Observable } from "rxjs";
import {
  Dashboard,
  DocumentDetail,
  DocumentSummary,
  GlossaryEntry,
  MemoryEntry,
  AuditEvent,
  TestingReport,
  AdminConfig,
  ReviewPayload,
  User,
} from "./models";
@Injectable({ providedIn: "root" })
export class ApiService {
  constructor(private readonly http: HttpClient) {}
  /**
   * Browser calls deliberately pass no token: the interceptor sends the
   * HttpOnly session cookie. Tests and legacy CLI callers may opt in to a
   * caller-supplied Bearer token without reintroducing browser token storage.
   */
  authOptions(legacyToken?: string): {
    withCredentials: true;
    headers?: HttpHeaders;
  } {
    const token = legacyToken?.trim();
    return token
      ? {
          withCredentials: true,
          headers: new HttpHeaders({ Authorization: `Bearer ${token}` }),
        }
      : { withCredentials: true };
  }
  me(): Observable<User> {
    return this.http.get<User>("/api/auth/me");
  }
  dashboard(): Observable<Dashboard> {
    return this.http.get<Dashboard>("/api/dashboard");
  }
  documents(): Observable<DocumentSummary[]> {
    return this.http.get<DocumentSummary[]>("/api/documents");
  }
  document(id: string): Observable<DocumentDetail> {
    return this.http.get<DocumentDetail>(
      `/api/documents/${encodeURIComponent(id)}`
    );
  }
  upload(file: File): Observable<DocumentDetail> {
    const data = new FormData();
    data.append("file", file, file.name);
    return this.http.post<DocumentDetail>("/api/documents", data);
  }
  analyze(id: string): Observable<DocumentDetail> {
    return this.http.post<DocumentDetail>(
      `/api/documents/${encodeURIComponent(id)}/analyze`,
      {}
    );
  }
  translate(id: string): Observable<DocumentDetail> {
    return this.http.post<DocumentDetail>(
      `/api/documents/${encodeURIComponent(id)}/translate`,
      {}
    );
  }
  review(id: string, payload: ReviewPayload): Observable<DocumentDetail> {
    return this.http.post<DocumentDetail>(
      `/api/documents/${encodeURIComponent(id)}/review`,
      payload
    );
  }
  artifact(id: string, kind: string): Observable<Blob> {
    return this.http.get(
      `/api/documents/${encodeURIComponent(id)}/artifact/${encodeURIComponent(kind)}`,
      { responseType: "blob" }
    );
  }
  preview(
    id: string,
    kind: string,
    page: number,
    version?: number
  ): Observable<Blob> {
    let params = new HttpParams();
    if (version !== undefined && version > 0)
      params = params.set("version", version);
    return this.http.get(
      `/api/documents/${encodeURIComponent(id)}/preview/${encodeURIComponent(kind)}/${page}`,
      { responseType: "blob", params }
    );
  }
  glossary(): Observable<GlossaryEntry[]> {
    return this.http.get<GlossaryEntry[]>("/api/glossary");
  }
  addGlossary(value: {
    source: string;
    target: string;
    domain: string;
  }): Observable<GlossaryEntry> {
    return this.http.post<GlossaryEntry>("/api/glossary", value);
  }
  memory(): Observable<MemoryEntry[]> {
    return this.http.get<MemoryEntry[]>("/api/memory");
  }
  addMemory(value: {
    source: string;
    target: string;
  }): Observable<MemoryEntry> {
    return this.http.post<MemoryEntry>("/api/memory", value);
  }
  testing(): Observable<TestingReport> {
    return this.http.get<TestingReport>("/api/testing");
  }
  audit(): Observable<AuditEvent[]> {
    return this.http.get<AuditEvent[]>("/api/audit");
  }
  admin(): Observable<AdminConfig> {
    return this.http.get<AdminConfig>("/api/admin");
  }
}
