# Livrables — industrialisation finale (09/10)

Code exécuté par le corpus golden et le passage final : empreinte `f69a6210b29e8196`. Code committé : empreinte `f2d0950f03f0d780`, qui ne diffère que par une docstring et dont l’AST est identique (définitions dans `REPRODUCTION.md` §1). La suite technique a été rejouée sur le code committé. Statut des 8 documents : `REVIEW_REQUIRED`. Aucun n’est déclaré PASS.

| § 17 | Livrable | Emplacement |
|---|---|---|
| 1 | Défauts, causes et corrections (D1 à D27) : symptôme, cause, fichier/fonction, correction, test, avant/après | `AUDIT_CORRECTIFS.md` |
| 2 | Tests passés, échoués et non exécutés, et correspondance avec les catégories du §16 | `TEST_REPORT.md` |
| 3 | Comparaison visuelle avant/après, mesures du §15, alertes critiques | `DOCUMENT_FIDELITY_REPORT.md` |
| 4 | Couverture par document, raisons de non-traduction, budget 32K | `TRANSLATION_COVERAGE_REPORT.md` |
| 5 | Métriques JSON | Anonymisées : `CORPUS_METRICS_FINAL.json`. Détaillées : répertoire privé (`$PRIVATE/metrics/`), hors Git. |
| 6 | Rendus comparatifs (original, ancienne traduction, nouvelle traduction, différences) | Répertoire privé `$PRIVATE/comparisons/run17-vs-baseline/` et archive privée, hors Git (données personnelles) |
| 7 | Fichiers source modifiés | `MODIFIED_FILES.md` |
| 8 | Instructions de reproduction | `REPRODUCTION.md` |
| 9 | Limites restant à corriger | `AUDIT_CORRECTIFS.md`, section « Défauts restants et limites » (1 à 18) |
| 10 | Dépendances et configurations supplémentaires | `REPRODUCTION.md` (dépendances, autorisation propriétaire, variables) |

Synthèse machine : `EXECUTION-RESULT.json`.

Les outils de recette sont versionnés dans `tools/recette/`. Ils refusent d’écrire dans le dépôt.
