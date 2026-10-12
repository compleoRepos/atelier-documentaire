# RUN25 — Fichiers modifiés

Base : commit `026b0f9` (verdict run18). Toutes les modifications ci-dessous sont incluses dans l'empreinte du code
exécuté par le run final `f4a84aaef38c7c7d`. Aucun fichier frontend, de dépendances, de déploiement ni de
migration n'est modifié (`git diff 026b0f9 -- frontend` vide).

## Code applicatif

| Fichier | Lignes (+/−) | Correctifs | Fonctions ajoutées ou modifiées |
|---|---|---|---|
| `backend/app/documents/pdf_fidelity.py` | +345 / −7 | F20, F20b, F22, F22b, F24 | ajoutées : `_vertical_ink_split` (F20), `_glyph_band` (F20b), `_longest_run` et `_clip_cover_off_rules` (F22), `_pull_padding_off_foreign_ink` (F24) ; modifiées : `_scan_covers` (paramètre `page`, partage F20, appels F24 puis F22), `_plan_scan_block` (ancrage F20b, `page=page` sur le masque complet F22b) |
| `backend/app/documents/line_verification.py` | +67 / −1 | F21, F23 | ajoutées : `flag_misread_checkbox_tokens` (F21), `flag_bidi_number_runs` (F23) ; modifiée : `verify_lines` (appels, compteurs) ; `VERSION` : `line-verification-7` → `line-verification-9` |

Les correctifs de rendu (F20 à F24) prévoient un repli : sans page raster, ou quand une condition n'est pas établie
(trait joignant deux lignes, attribution ambiguë, filet non continu), le comportement antérieur s'applique.

F21 et F23 ne font que retirer des blocs de la traduction : ils marquent l'OCR comme non fiable, le bloc passe en
`UNCERTAIN` et l'original est conservé.

Ne sont pas modifiés : le plancher de police, la garde de budget de 32K, le seuil de confiance OCR existant et les
seuils de rendu.

## Outils de recette (versionnés, sans données)

| Fichier | Lignes | Rôle |
|---|---|---|
| `tools/recette/anomaly_register.py` | 179 (nouveau) | registre d'anomalies par bloc. Il reprend les règles de `measure_v2` (périmètre attendu indépendant du run, statuts, rendu mesuré dans le PDF) et écrit une ligne par bloc défectueux : document, page, bloc, coordonnées, codes, statut, sans texte. La sortie est refusée si sa destination se trouve dans le dépôt |

## Tests

| Fichier | Tests | Couverture |
|---|---|---|
| `backend/tests/unit/test_run25_regressions.py` | 19 (nouveau, 385 lignes) | F20 ×4, F20b ×2, F21 ×2, F22 ×4, F22b ×1, F23 ×2, F24 ×4 ; pages et blocs entièrement synthétiques |

Contre-épreuves effectuées (correctif neutralisé, le test doit échouer) :

* `test_f22b_plan_full_cover_stays_off_frame_rules` échoue sans F22b ;
* le cas positif F23 échoue sans F23 ;
* 3 des 4 tests F24 échouent sans F24, et le 4e, cas négatif, réussit.

## Rapports (ce répertoire)

`README.md`, `RUN25_ROOT_CAUSE_ANALYSIS.md`, `RUN25_REGRESSION_REPORT.md`, `RUN25_DOCUMENT_FIDELITY_REPORT.md`,
`RUN25_TRANSLATION_COVERAGE_REPORT.md`, `MODIFIED_FILES.md`, `TEST_RESULTS.md`, `LIMITATIONS.md`,
`REPRODUCTION.md`, `metrics/RUN25_METRICS_BY_DOCUMENT.json`, `metrics/RUN25_LIVE_GENERATION_CHECK.json`.

## Hors dépôt (privé, jamais versionné)

* Originaux, OCR, IR, PDF produits, planches et recadrages.
* Autorisation du propriétaire, scripts de run, outils de relecture instrumentée et de mesure du débord de masque.
* Journaux de tests et notes.

Ces éléments sont conservés dans l'espace privé de la recette et dans l'archive privée de preuves.
