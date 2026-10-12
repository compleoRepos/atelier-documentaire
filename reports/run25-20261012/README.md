# Recette run25 — 12/10/2026

Recette industrielle des 8 PDF originaux autorisés, menée à partir du verdict run18 (commit `026b0f9`, run24).
Elle couvre la correction des causes réelles des défauts de reconstruction restants, avec une priorité sur DOC-004,
DOC-007 et DOC-008, puis DOC-005, et la non-régression des autres documents.

## Verdict

**`REVIEW_REQUIRED` pour les 8 documents. Aucun document n'est déclaré conforme ni PASS.**

| Indicateur (8 documents, même méthode) | baseline | run17 | run24 | **run25** |
|---|---|---|---|---|
| Couverture écrite | 0,8365 | 0,8195 | 0,8364 | **0,8419** |
| Caractères absents (tentés mais introuvables dans le PDF) | 2 342 | 3 341 | 2 842 | **2 374** |
| Mots insérés en collision | — | 34 | 0 | **0** |
| `SCAN_TEXT_OVER_SOURCE_INK` | 0 | 25 | 19 | **9** |
| Régions graphiques altérées | 63 | 89 | 83 | **81** |
| Encre originale effacée hors des blocs écrits (px) | — | — | 13 117 | **6 573** |
| Cachets, signatures et logos modifiés | — | — | 0 | **0** |
| Cases à cocher de DOC-004 modifiées (sur 27) | 7 | 9 | 0 | **0** |

* Les écarts de run24 à run25 sont attribuables au **seul code** : les traductions sont identiques, servies par la
  mémoire de run24, avec 0 requête au moteur IA.
* Un run supplémentaire à génération Interim réelle (63 requêtes, 0 violation du budget de 32K) montre une variance de
  génération de 71,6 % des caractères. Il n'est pas le verdict.
* **Correctifs** : F20, F20b, F21, F22, F22b, F23 et F24.
* **Effet par document** :
  * DOC-004 : couverture écrite de 0,538 à 0,589 ;
  * DOC-007 : de 0,763 à 0,778 ;
  * DOC-008 : de 0,640 à 0,591. C'est une baisse **volontaire** : des numéros dont les groupes étaient inversés ne
    sont plus rendus, et l'original est conservé ;
  * DOC-005, DOC-006, DOC-001, DOC-002 et DOC-003 : couverture identique, et moins d'encre effacée.
* **Critères d'acceptation non atteints ou non mesurés** :
  * la structure des tableaux n'est pas mesurée par le moteur ;
  * les données critiques et les éléments graphiques ne sont que partiellement préservés.

  Le détail figure dans `RUN25_REGRESSION_REPORT.md` §7.

## Livrables (prompt run25 §18)

| N° | Livrable | Fichier |
|---|---|---|
| 1 | Analyse des causes racines (symptôme, cause, fichier et fonction, correction, test, avant/après) | `RUN25_ROOT_CAUSE_ANALYSIS.md` |
| 2 | Rapport de régression (baseline, run17, run24, run25) | `RUN25_REGRESSION_REPORT.md` |
| 3 | Rapport de fidélité documentaire | `RUN25_DOCUMENT_FIDELITY_REPORT.md` |
| 4 | Rapport de couverture de traduction | `RUN25_TRANSLATION_COVERAGE_REPORT.md` |
| 5 | Métriques JSON détaillées (anonymisées) | `metrics/RUN25_METRICS_BY_DOCUMENT.json`, `metrics/RUN25_LIVE_GENERATION_CHECK.json` |
| 6 | Rendus et diffs visuels | **archive privée de preuves**, hors Git : planches multi-runs, audits des régions, recadrages, mesures de filets et de débord |
| 7 | Fichiers source modifiés | `MODIFIED_FILES.md` |
| 8 | Résultats des tests | `TEST_RESULTS.md` |
| 9 | Limites restantes | `LIMITATIONS.md` |
| 10 | Instructions de reproduction | `REPRODUCTION.md` |

## Validation

| Contrôle | Résultat |
|---|---|
| Backend, périmètre exact de la CI | 610 passed, 0 failed (code `f4a84aaef38c7c7d`) |
| Golden local | 8 passed (même code) |
| Frontend | typecheck, 16 tests, build et `npm audit` OK (frontend inchangé) |
| Ruff, pip-audit | OK |
| CI GitHub | `success` sur le SHA exact `c14197d` (backend 610 passed, intégration 28 passed, frontend, conteneurs et Helm) ; gates privés `skipped` ; voir `TEST_RESULTS.md` §8 |

## Confidentialité

Ce répertoire ne contient aucun texte de document, nom de fichier, empreinte de document, image, chemin privé ni
secret.

* Les documents sont désignés par DOC-001 à DOC-008 et les blocs par leur identifiant de position.
* Les originaux, OCR, IR, PDF produits, planches et l'autorisation du propriétaire restent privés.
* Interim est un moteur temporaire de développement : ses résultats ne valent pas validation de Qwen.
