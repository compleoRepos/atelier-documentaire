# Run18 — Correction des régressions run17 (index des livrables)

Branche `feature/run18-regressions-20261011`, code de départ `ebb09eb`. Verdict run18 = passage `run24`,
empreinte du code `4d4956273c97d866` (SHA-256 des sources Python de `backend/app` et `tools`).

**Statut : les 8 documents sont `REVIEW_REQUIRED`.** Aucune référence humaine n'existe ; des alertes réelles
subsistent ; aucun résultat n'est présenté comme PASS. Les traductions viennent du moteur temporaire
**Interim** (gpt-5-mini), sous budget 32 768 tokens par requête (0 violation) ; ce ne sont pas des résultats
Qwen.

## Résultat en bref

| Indicateur (même méthode `measure-v2.1-run18`) | baseline | run17 | run18 |
|---|---|---|---|
| Couverture écrite totale | 0,8365 | 0,8195 | 0,8364 |
| DOC-004 / DOC-005 / DOC-007 (priorité 1) | 0,717 / 0,044 / 0,796 | 0,361 / 0,155 / 0,710 | 0,538 / 0,454 / 0,763 |
| DOC-001 / DOC-002 (priorité 2) | 0,598 / 0,434 | 0,555 / 0,273 | 0,576 / 0,393 |
| DOC-006 / DOC-008 (non-régression) | 0,913 / 0,547 | 0,953 / 0,646 | 0,937 / 0,640 |
| Mots insérés en collision | 0 | 34 | 0 |
| Régions de cases altérées (DOC-004, 27 cases) | 7 | 9 | 0 |

DOC-004, DOC-002, DOC-001 et DOC-007 restent sous la baseline : voir `RUN18_REGRESSION_REPORT.md` et
`LIMITATIONS.md`.

## Validation

| Contrôle | Résultat |
|---|---|
| Suite backend (périmètre CI), local | 591 passed, 0 failed |
| Golden local (8 originaux, contrôle technique) | 8 passed |
| CI GitHub [38176137547](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/38176137547), SHA `1069303` | success (backend 591, frontend 16, intégration/migrations 28, conteneurs) ; portes privées SKIPPED |

## Livrables (prompt §14)

| # | Livrable demandé | Fichier |
|---|---|---|
| 1 | Analyse des causes racines | [`RUN18_ROOT_CAUSE_ANALYSIS.md`](RUN18_ROOT_CAUSE_ANALYSIS.md) |
| 2 | Comparaison baseline / run17 / run18 | [`RUN18_REGRESSION_REPORT.md`](RUN18_REGRESSION_REPORT.md) |
| 3 | Fidélité documentaire | [`RUN18_DOCUMENT_FIDELITY_REPORT.md`](RUN18_DOCUMENT_FIDELITY_REPORT.md) |
| 4 | Couverture de traduction et statuts par bloc | [`RUN18_TRANSLATION_COVERAGE_REPORT.md`](RUN18_TRANSLATION_COVERAGE_REPORT.md) |
| 5 | Fichiers modifiés | [`MODIFIED_FILES.md`](MODIFIED_FILES.md) |
| 6 | Résultats des tests | [`TEST_RESULTS.md`](TEST_RESULTS.md) |
| 7 | Limites connues | [`LIMITATIONS.md`](LIMITATIONS.md) |
| 8 | Métriques anonymisées par document | [`metrics/RUN18_METRICS_BY_DOCUMENT.json`](metrics/RUN18_METRICS_BY_DOCUMENT.json) |

Outils de mesure versionnés (sans données) : `tools/recette/render_outcome.py`, `tools/recette/measure_v2.py`,
`tools/recette/compare_runs_sheets.py`. Ils refusent d'écrire leurs sorties dans le dépôt.

## Confidentialité

Aucun original, OCR, IR, image, rendu, nom de fichier, SHA réel, texte de document, autorisation ni secret
n'est versionné. Les preuves (sorties PDF, planches comparatives, zooms, diagnostics bloc par bloc,
journaux de tests, mesures brutes) sont conservées **hors Git**, à accès restreint, sous des identifiants
abstraits `DOC-001` à `DOC-008`. L'usage de Interim sur les originaux repose sur une autorisation du
propriétaire, nominative par empreinte, expirante et conservée hors Git.
