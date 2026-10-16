# RUN27 — Avant / après

« Avant » = **run26** (verdict RUN26, artefacts run26b). « Après » = **run27** (verdict RUN27, artefacts run27b). Même corpus de huit originaux (empreintes SHA-256 inchangées avant/après chaque run), mêmes entrées, même méthode gelée (`doc-confidence-2` / `scorecard-2`, et `doc-confidence-1` / `scorecard-1` pour la continuité). Toutes les comparaisons sont faites **à règle de mesure identique** (voir RUN27-SCORE-AUDIT.md § 4). La règle de référence est la règle RUN27 ; la règle RUN26 pure est donnée en contrôle.

## 1. Corpus

| Run | v2 — règle RUN27 : basse [haute] plafond | v2 — règle RUN26 pure | v1 — règle RUN27 | v1 — règle RUN26 | v1 publié RUN26 |
| --- | --- | --- | --- | --- | --- |
| baseline | 59,2 [86,5] C 72,7 | 59,2 [86,5] C 72,7 | 63,1 | 63,1 | 63,1 |
| run24 | 63,1 [87,4] C 75,8 | 64,6 [88,9] C 75,8 | 66,1 | 67,9 | 67,9 |
| run25 | 63,2 [87,5] C 75,8 | 64,6 [88,9] C 75,8 | 66,1 | 68,0 | 68,0 |
| run26 | 63,5 [87,8] C 75,8 | 64,9 [89,2] C 75,8 | 71,9 | 73,8 | 73,8 |
| run27 | 65,9 [90,2] C 75,8 | 67,2 [91,5] C 75,8 | 74,6 | 75,8 | — |

- Score officiel v2 (règle RUN27) : **63,5 → 65,9** (+2,39 exact), borne haute 87,8 → 90,2, plafond 75,8 inchangé (aucune référence humaine ajoutée).
- Contrôle règle RUN26 pure : 64,9 → 67,2. La v1 publiée par RUN26 (73,8) est reproduite ; la v1 RUN27 serait 75,8 (règle RUN26) ou 74,6 (règle RUN27). La v1 n’est plus le score de référence : ses points de preuves ne mesurent pas la qualité.
- **Seuil 94 non atteint**, ni en borne basse ni par aucun document ; il est inaccessible sans références humaines.

## 2. Par document (v2, règle RUN27, borne basse)

| Document | baseline | run24 | run25 | run26 | run27 |
| --- | --- | --- | --- | --- | --- |
| DOC-001 | 64,9 | 61,3 | 61,3 | 63,1 | 63,1 |
| DOC-002 | 59,9 | 60,5 | 60,3 | 60,3 | 66,7 |
| DOC-003 | 18,7 | 62,7 | 62,7 | 62,7 | 62,7 |
| DOC-004 | 67,5 | 63,3 | 64,6 | 65,1 | 66,2 |
| DOC-005 | 52,0 | 47,7 | 47,7 | 47,7 | 58,3 |
| DOC-006 | 74,6 | 73,2 | 73,2 | 73,2 | 73,4 |
| DOC-007 | 69,8 | 69,0 | 69,6 | 69,4 | 70,3 |
| DOC-008 | 65,8 | 67,3 | 66,2 | 66,4 | 66,4 |

Contrôle à règle RUN26 pure (v2) et v1 :

| Document | v2 baseline | v2 run24 | v2 run25 | v2 run26 | v2 run27 | v1 run26 | v1 run27 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 64,9 | 61,3 | 61,3 | 63,1 | 63,1 | 72,0 | 72,0 |
| DOC-002 | 59,9 | 60,5 | 60,3 | 60,3 | 66,7 | 70,6 | 75,4 |
| DOC-003 | 18,7 | 62,7 | 62,7 | 62,7 | 62,7 | 71,4 | 71,4 |
| DOC-004 | 67,5 | 63,3 | 64,6 | 65,1 | 66,2 | 74,5 | 75,3 |
| DOC-005 | 52,0 | 59,3 | 59,3 | 59,3 | 68,9 | 67,3 | 77,1 |
| DOC-006 | 74,6 | 73,2 | 73,2 | 73,2 | 73,4 | 81,2 | 81,2 |
| DOC-007 | 69,8 | 69,0 | 69,6 | 69,4 | 70,3 | 78,1 | 78,7 |
| DOC-008 | 65,8 | 67,3 | 66,2 | 66,4 | 66,4 | 75,2 | 75,2 |

## 3. D’où vient le gain (v2, règle RUN27, points de borne basse run26 → run27)

| Document | Couverture | Traduction | Fidélité source | Entités | Mise en page | OCR | Hallucination | Δ borne basse |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | +0,00 |
| DOC-002 | +5,58 | 0 | -0,20 | +0,93 | +0,05 | 0 | +0,03 | +6,39 |
| DOC-003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | +0,00 |
| DOC-004 | +0,84 | -0,01 | 0 | 0 | +0,19 | 0 | -0,00 | +1,03 |
| DOC-005 | 0 | 0 | -0,03 | +8,33 | +2,22 | 0 | 0 | +10,53 |
| DOC-006 | 0 | 0 | 0 | +0,14 | +0,10 | 0 | 0 | +0,24 |
| DOC-007 | +0,68 | -0,01 | -0,01 | +0,08 | +0,22 | 0 | -0,00 | +0,96 |
| DOC-008 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | +0,00 |
| **Moyenne corpus** | +0,89 | -0,00 | -0,03 | +1,19 | +0,35 | +0,00 | +0,00 | +2,39 |

| Document | Lecture |
| --- | --- |
| DOC-001 | 0 : **PDF identique** au pixel près. Aucune amélioration revendiquée. |
| DOC-002 | +6,39 : bloc P0 traduit (F29 A), chiffres identiques, contrôlé sur le PDF ; la couverture écrite passe de 39,3 % à 64,4 %. |
| DOC-003 | 0 : **PDF identique**. Aucune amélioration revendiquée. |
| DOC-004 | +1,03 : 3 blocs rendus grâce à F30/F31 (contrôlés sur planche) ; un débordement de moins parce qu’un bloc est passé en revue, pas parce qu’il a été corrigé. |
| DOC-005 | +10,53, dont **+8,33 d’artefact** (entités comparées à l’OCR fausse : régression MV-01) et +2,22 de mise en page (alertes de rendu disparues avec le reclassement F33 de la ligne déjà française). **Gain non revendiqué** : le PDF contient un identifiant faux de plus qu’en run26. |
| DOC-006 | +0,24 : alertes d’entités et de masques disparues ; les 24 alertes de masques étaient des erreurs de calcul (F32). Le PDF change sur 2 pages (masques), le tampon est intact. |
| DOC-007 | +0,96 : blocs rendus (F30/F31, dont la régression F25 de RUN26 corrigée), cases cochées préservées (MV-02). |
| DOC-008 | 0 : 6 octets de différence, **aucun changement visible**. Aucune amélioration revendiquée. |

Sensibilité (non officielle) : sans l’artefact DOC-005, le corpus serait à 64,89 (+1,35).

## 4. Défauts critiques

Mesurés par la v2 (alertes critiques du produit, dédupliquées par famille) :

| Code | run26 | run27 | Δ | Cause de la variation |
| --- | --- | --- | --- | --- |
| `CRITICAL_ENTITY_MODIFIED` | 2 | 0 | -2 | F29 D (date collée) + garde entités |
| `ENTITY_DIGITS_MISMATCH` | 1 | 0 | -1 | F29 A (contrôle symétrique) — mais voir MV-01 |
| `HALLUCINATION_ENTITY_MODIFIED` | 1 | 0 | -1 | F29 D |
| `HALLUCINATION_UNIT_CHANGED` | 1 | 0 | -1 | F29 C (unités FR accentuées) |
| `LAYOUT_OVERFLOW` | 29 | 28 | -1 | DOC-004 : un bloc passé en revue (F29 B) — non corrigé sur le fond |
| `PROTECTED_ENTITY_CHANGED` | 3 | 0 | -3 | F29 A/B (nombre collé protégé ; OCR bruitée en revue) |
| `PROTECTED_REGION_CHANGED` | 6 | 6 | 0 | non corrigé |
| `RENDER_SOURCE_TEXT_MISSING` | 7 | 6 | -1 | DOC-005 : F33 (ligne déjà française reclassée) |
| `RENDER_TEXT_CLIPPED_OR_MISSING` | 7 | 6 | -1 | idem |
| `RENDER_TEXT_MASK_TOO_LARGE` | 15 | 0 | -15 | F32 : aire de l’union (double comptage supprimé) — mesure corrigée, masques quasi inchangés |
| `RENDER_TRANSLATED_TEXT_MISSING` | 7 | 6 | -1 | idem |
| `SCAN_TEXT_OVER_SOURCE_INK` | 10 | 2 | -8 | F30/F31 : masques réellement modifiés (contrôlé sur planches) |
| `UNMAPPED_TABLE_CONTENT` | 1 | 1 | 0 | non corrigé |
| `VISUAL_MASK_TOO_LARGE` | 15 | 0 | -15 | F32 (idem, scorer visuel) |
| **Total** | 105 | 55 | -50 |  |

Ventilation exacte des 50 alertes critiques en moins (30 + 8 + 8 + 3 + 1) :

- **30 corrections de mesure** (masques, F32) : les masques n’ont pas changé, ce n’est pas un progrès du rendu ;
- **8 alertes d’entités** : faux positifs d’unité et de date supprimés (F29 C/D), blocs désormais traduits avec des chiffres identiques (F29 A), blocs OCR bruités envoyés en revue (F29 B). **Exception** : `ENTITY_DIGITS_MISMATCH` de DOC-005 disparaît pour une **mauvaise raison** (la cible reproduit maintenant l’erreur d’OCR : MV-01) ;
- **8 encres résiduelles** corrigées et contrôlées sur le PDF (F30/F31) ;
- **3 alertes de rendu** de DOC-005 disparues parce que la ligne déjà française n’est plus comptée comme traduite (F33) ;
- **1 débordement** de DOC-004 disparu parce que le bloc est passé en revue humaine (F29 B), sans correction du débordement.

Par document :

| Document | Codes critiques mesurés (run26 → run27) |
| --- | --- |
| DOC-001 | `RENDER_SOURCE_TEXT_MISSING` 1→1, `RENDER_TEXT_CLIPPED_OR_MISSING` 1→1, `RENDER_TRANSLATED_TEXT_MISSING` 1→1 |
| DOC-002 | `PROTECTED_ENTITY_CHANGED` 1→0, `RENDER_SOURCE_TEXT_MISSING` 1→1, `RENDER_TEXT_CLIPPED_OR_MISSING` 1→1, `RENDER_TRANSLATED_TEXT_MISSING` 1→1, `SCAN_TEXT_OVER_SOURCE_INK` 1→1 |
| DOC-003 | aucun |
| DOC-004 | `LAYOUT_OVERFLOW` 17→16, `PROTECTED_REGION_CHANGED` 6→6, `RENDER_SOURCE_TEXT_MISSING` 1→1, `RENDER_TEXT_CLIPPED_OR_MISSING` 1→1, `RENDER_TEXT_MASK_TOO_LARGE` 1→0, `RENDER_TRANSLATED_TEXT_MISSING` 1→1, `SCAN_TEXT_OVER_SOURCE_INK` 3→0, `VISUAL_MASK_TOO_LARGE` 1→0 |
| DOC-005 | `ENTITY_DIGITS_MISMATCH` 1→0, `RENDER_SOURCE_TEXT_MISSING` 1→0, `RENDER_TEXT_CLIPPED_OR_MISSING` 1→0, `RENDER_TRANSLATED_TEXT_MISSING` 1→0, `SCAN_TEXT_OVER_SOURCE_INK` 1→0 |
| DOC-006 | `CRITICAL_ENTITY_MODIFIED` 2→0, `HALLUCINATION_ENTITY_MODIFIED` 1→0, `HALLUCINATION_UNIT_CHANGED` 1→0, `LAYOUT_OVERFLOW` 3→3, `PROTECTED_ENTITY_CHANGED` 1→0, `RENDER_SOURCE_TEXT_MISSING` 1→1, `RENDER_TEXT_CLIPPED_OR_MISSING` 1→1, `RENDER_TEXT_MASK_TOO_LARGE` 12→0, `RENDER_TRANSLATED_TEXT_MISSING` 1→1, `SCAN_TEXT_OVER_SOURCE_INK` 1→1, `VISUAL_MASK_TOO_LARGE` 12→0 |
| DOC-007 | `LAYOUT_OVERFLOW` 7→7, `PROTECTED_ENTITY_CHANGED` 1→0, `RENDER_SOURCE_TEXT_MISSING` 1→1, `RENDER_TEXT_CLIPPED_OR_MISSING` 1→1, `RENDER_TEXT_MASK_TOO_LARGE` 2→0, `RENDER_TRANSLATED_TEXT_MISSING` 1→1, `SCAN_TEXT_OVER_SOURCE_INK` 4→0, `UNMAPPED_TABLE_CONTENT` 1→1, `VISUAL_MASK_TOO_LARGE` 2→0 |
| DOC-008 | `LAYOUT_OVERFLOW` 2→2, `RENDER_SOURCE_TEXT_MISSING` 1→1, `RENDER_TEXT_CLIPPED_OR_MISSING` 1→1, `RENDER_TRANSLATED_TEXT_MISSING` 1→1 |

Vérifiés à l’œil sur les PDF (non vus par les métriques) :

| Document | Id | Défaut | Gravité | run26 → run27 | Vu par les métriques | Statut |
| --- | --- | --- | --- | --- | --- | --- |
| DOC-005 | MV-01 | `IDENTIFIER_ALTERED_VS_ORIGINAL_IMAGE` | critical | 0 → 1 | non | OPEN_REGRESSION_RUN27 |
| DOC-007 | MV-02 | `CHECKBOX_STATE_LOST` | critical | 2 → 0 | non | FIXED_RUN27 (blocs mis en revue humaine, original conservé) |
| DOC-007 | MV-03 | `RESIDUAL_SOURCE_WORDS_IN_TRANSLATED_LINE` | major | 1 → 1 | non | OPEN_PREEXISTING |

## 5. Couverture et statuts de blocs

Caractères attendus, écrits, partiellement écrits, absents et non tentés (mesure v2.1, règle RUN27) :

| Document | Car. attendus (run27) | Écrits | Partiels | Absents | Non tentés | Couverture écrite | Blocs par statut (run27) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 624 | 367 → 367 | 0 → 0 | 93 → 93 | 164 → 164 | 58,8 % → 58,8 % | FAILED 3, NOT_PROCESSED 0, NOT_TRANSLATABLE 10, PRESERVED_INTENTIONALLY 19, TRANSLATED 9, UNCERTAIN 6 |
| DOC-002 | 820 | 322 → 528 | 0 → 0 | 133 → 133 | 365 → 159 | 39,3 % → 64,4 % | FAILED 6, NOT_PROCESSED 0, NOT_TRANSLATABLE 2, PRESERVED_INTENTIONALLY 3, TRANSLATED 9, UNCERTAIN 4 |
| DOC-003 | 81 | 60 → 60 | 0 → 0 | 0 → 0 | 21 → 21 | 74,1 % → 74,1 % | FAILED 1, NOT_PROCESSED 0, NOT_TRANSLATABLE 0, PRESERVED_INTENTIONALLY 10, TRANSLATED 2, UNCERTAIN 0 |
| DOC-004 | 3549 | 2058 → 2193 | 99 → 99 | 858 → 643 | 534 → 614 | 58,0 % → 61,8 % | FAILED 29, NOT_PROCESSED 0, NOT_TRANSLATABLE 41, PRESERVED_INTENTIONALLY 11, TRANSLATED 91, UNCERTAIN 57 |
| DOC-005 | 366 | 78 → 78 | 0 → 0 | 0 → 0 | 288 → 288 | 21,3 % → 21,3 % | FAILED 7, NOT_PROCESSED 0, NOT_TRANSLATABLE 25, PRESERVED_INTENTIONALLY 50, TRANSLATED 2, UNCERTAIN 5 |
| DOC-006 | 26942 | 25242 → 25242 | 45 → 45 | 161 → 161 | 1494 → 1494 | 93,7 % → 93,7 % | FAILED 51, NOT_PROCESSED 0, NOT_TRANSLATABLE 36, PRESERVED_INTENTIONALLY 19, TRANSLATED 268, UNCERTAIN 44 |
| DOC-007 | 8974 | 6874 → 7147 | 82 → 82 | 867 → 338 | 1151 → 1407 | 76,6 % → 79,6 % | FAILED 27, NOT_PROCESSED 0, NOT_TRANSLATABLE 22, PRESERVED_INTENTIONALLY 8, TRANSLATED 89, UNCERTAIN 32 |
| DOC-008 | 1741 | 1029 → 1029 | 0 → 0 | 228 → 228 | 484 → 484 | 59,1 % → 59,1 % | FAILED 18, NOT_PROCESSED 0, NOT_TRANSLATABLE 5, PRESERVED_INTENTIONALLY 27, TRANSLATED 22, UNCERTAIN 2 |

- Couverture écrite du corpus pondérée par les caractères : 83,6 % → 85,0 % (le score, lui, pondère chaque document également).
- Les blocs non traduits restent visibles : `FAILED` (refus de rendu, garde, ordinal), `UNCERTAIN` (OCR non fiable, revue humaine), `NOT_TRANSLATABLE`, `PRESERVED_INTENTIONALLY` ; `NOT_PROCESSED` = 0.

## 6. PDF

| Document | Pages | Pages modifiées (pixels) | Pages à changement visible | Conclusion |
| --- | --- | --- | --- | --- |
| DOC-001 | 2 | aucune | aucune | **PDF identique : aucune amélioration revendiquée** |
| DOC-002 | 1 | 1 | 1 | contrôlé sur planches privées |
| DOC-003 | 1 | aucune | aucune | **PDF identique : aucune amélioration revendiquée** |
| DOC-004 | 2 | 1, 2 | 1, 2 | contrôlé sur planches privées |
| DOC-005 | 2 | 2 | 2 | contrôlé sur planches privées |
| DOC-006 | 16 | 2, 16 | 16 | contrôlé sur planches privées |
| DOC-007 | 5 | 1, 3 | 1, 3 | contrôlé sur planches privées |
| DOC-008 | 2 | 2 | aucune | contrôlé sur planches privées |

Les pages modifiées ont été comparées sur planches privées original | run26 | run27, zone par zone (16 zones). Les planches de l’ensemble des runs (baseline, run17, run24, run25, run26, run27) sont dans l’espace privé autorisé, jamais dans Git.

## 7. Provenance et budget (run verdict)

| Document | Mode de génération | Modèle invoqué | Requêtes run27b | Réservation max (tokens) | Violations budget | Origine des blocs | Réutilisations invalidées |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | `TRANSLATION_MEMORY_REUSE_ONLY` | non | 0 | — | 0 | TRANSLATION_MEMORY 47 | 0 |
| DOC-002 | `TRANSLATION_MEMORY_REUSE_ONLY` | non | 0 | — | 0 | TRANSLATION_MEMORY 24 | 0 |
| DOC-003 | `TRANSLATION_MEMORY_REUSE_ONLY` | non | 0 | — | 0 | TRANSLATION_MEMORY 13 | 0 |
| DOC-004 | `TRANSLATION_MEMORY_REUSE_ONLY` | non | 0 | — | 0 | TRANSLATION_MEMORY 229 | 0 |
| DOC-005 | `TRANSLATION_MEMORY_REUSE_ONLY` | non | 0 | — | 0 | TRANSLATION_MEMORY 89 | 0 |
| DOC-006 | `MIXED_MEMORY_AND_NEW_GENERATION` | oui | 1 | 16295 | 0 | MODEL_CALL 1, TRANSLATION_MEMORY 417 | 1 |
| DOC-007 | `TRANSLATION_MEMORY_REUSE_ONLY` | non | 0 | — | 0 | TRANSLATION_MEMORY 178 | 0 |
| DOC-008 | `TRANSLATION_MEMORY_REUSE_ONLY` | non | 0 | — | 0 | TRANSLATION_MEMORY 74 | 0 |

- run27b : **1 requête Interim** (DOC-006, le bloc dont l’ordinal est refusé), réservation maximale 16 295 ≤ 32 768 tokens, 0 violation de budget. Les 7 autres documents sont servis par la mémoire, revalidée par la garde courante (`model_invoked = False`).
- RUN27 au total : 5 requêtes (run intermédiaire run27 : 4, run27b : 1), sous l’autorisation privée RUN27 (8 empreintes revérifiées, expiration 6 h, hors Git).
