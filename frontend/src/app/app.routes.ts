import { Routes } from "@angular/router";
import { authGuard, roleGuard } from "./core/guards";
import { LoginPage } from "./pages/login.page";
import { DashboardPage } from "./pages/dashboard.page";
import { DocumentsPage } from "./pages/documents.page";
import { UploadPage } from "./pages/upload.page";
import { DocumentDetailPage } from "./pages/document-detail.page";
import { ReviewPage } from "./pages/review.page";
import { GlossaryPage } from "./pages/glossary.page";
import { MemoryPage } from "./pages/memory.page";
import { AdminPage } from "./pages/admin.page";
import { TestingPage } from "./pages/testing.page";
import { AuditPage } from "./pages/audit.page";
export const appRoutes: Routes = [
  {
    path: "login",
    component: LoginPage,
    title: "Connexion — Atelier documentaire",
  },
  {
    path: "dashboard",
    component: DashboardPage,
    canActivate: [authGuard],
    title: "Vue d’ensemble — Atelier documentaire",
  },
  {
    path: "documents",
    component: DocumentsPage,
    canActivate: [authGuard],
    title: "Documents — Atelier documentaire",
  },
  {
    path: "upload",
    component: UploadPage,
    canActivate: [authGuard],
    title: "Importer — Atelier documentaire",
  },
  {
    path: "documents/:id",
    component: DocumentDetailPage,
    canActivate: [authGuard],
    title: "Détail — Atelier documentaire",
  },
  {
    path: "review/:id",
    component: ReviewPage,
    canActivate: [authGuard, roleGuard(["admin", "reviewer"])],
    title: "Revue — Atelier documentaire",
  },
  {
    path: "glossary",
    component: GlossaryPage,
    canActivate: [authGuard],
    title: "Glossaire — Atelier documentaire",
  },
  {
    path: "translation-memory",
    component: MemoryPage,
    canActivate: [authGuard],
    title: "Mémoire — Atelier documentaire",
  },
  {
    path: "admin",
    component: AdminPage,
    canActivate: [authGuard, roleGuard(["admin"])],
    title: "Administration — Atelier documentaire",
  },
  {
    path: "testing",
    component: TestingPage,
    canActivate: [authGuard],
    title: "Essais — Atelier documentaire",
  },
  {
    path: "audit",
    component: AuditPage,
    canActivate: [authGuard],
    title: "Audit — Atelier documentaire",
  },
  { path: "", pathMatch: "full", redirectTo: "dashboard" },
  { path: "**", redirectTo: "dashboard" },
];
