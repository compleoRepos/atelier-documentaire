# RUN28 — Avant / après (RUN27 → RUN28)

> Avant = verdict RUN27 (run27b). Après = verdict RUN28 (run28e). Mêmes huit originaux, inchangés à chaque exécution. Toutes les valeurs proviennent des exports anonymisés `documents/*.json`.

## 1. Règles de mesure et reproductibilité

| Règle | Empreinte (`ruler_fingerprint`) | Code mesuré | run27 (corpus v2) | run28 (corpus v2) |
| --- | --- | --- | --- | --- |
| RUN27 | `aa3883b0360e2dd6` | arbre propre de la tête RUN27 `54bf5f2` | **65,9358 [90,1257]**, identique à la valeur publiée en RUN27 | 65,7063 [90,2433] |
| RUN28 | `08e998169c0dad9b` | arbre RUN28 mesuré (code `25dbea622c921535`, commit local `38b73c0` ; l’arbre poussé est AST-identique, règle `b827d913b8a71d88` par simple expurgation de commentaires) | 65,9330 [90,1229] | 65,7063 [90,2433] |

- Les méthodes (`doc-confidence-1`, `doc-confidence-2`, `measure-v2.1`) et `tools/recette` sont inchangés. Les gels v1 (RUN26) et v2 (RUN27) ont été revérifiés.
- La règle change parce que RUN28 modifie des statuts de blocs (F35, F39, F40, F41) lus par la mesure. Sur les runs historiques, l’écart entre les deux règles est ≤ 0,025 point (effet F40 sur trois blocs de DOC-004). Sur run28, les deux règles donnent la même valeur.
- Vérificateur indépendant : v2, écart maximal de 1,42 × 10⁻¹⁴ sur les deux règles et les six runs mesurés. v1, écart maximal < 0,05, égal à l’arrondi au dixième des valeurs stockées (run28 exact : 73,8734, stocké 73,9).

## 2. Tableau par document (règle RUN27 pour les deux colonnes)

| Document | v2 run27 → run28 [borne haute run28] | v1 run27 → run28 | Défauts critiques scorecard-2 | Alertes produit critiques | Débordements (blocs) | Couverture écrite | Pages modifiées vs RUN27 | Revue humaine | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 63,1 → **62,7** [86,0] | 72,0 → 71,7 | 3 → 3 | 6 → 6 | 0 → 0 | 58,8 % → 51,0 % | p. 2 / 2 | NOT_STARTED (0/47) | **REVIEW_REQUIRED** |
| DOC-002 | 66,7 → **66,7** [89,9] | 75,4 → 75,4 | 4 → 4 | 8 → 8 | 0 → 0 | 64,4 % → 64,4 % | aucune (pixel-identique) / 1 | NOT_STARTED (0/24) | **REVIEW_REQUIRED** |
| DOC-003 | 62,7 → **62,7** [94,2] | 71,4 → 71,4 | 0 → 0 | 0 → 0 | 0 → 0 | 74,1 % → 74,1 % | aucune (pixel-identique) / 1 | NOT_STARTED (0/13) | **REVIEW_REQUIRED** |
| DOC-004 | 66,2 → **67,0** [90,2] | 75,3 → 75,8 | 25 → 19 | 47 → 35 | 16 → 9 | 61,8 % → 64,4 % | p. 1, 2 / 2 | NOT_STARTED (0/229) | **REVIEW_REQUIRED** |
| DOC-005 | 58,3 → **53,0** [79,0] | 67,5 → 59,1 | 0 → 0 | 0 → 0 | 0 → 0 | 21,3 % → 9,8 % | p. 1, 2 / 2 | NOT_STARTED (0/89) | **REVIEW_REQUIRED** |
| DOC-006 | 73,4 → **73,5** [96,8] | 81,2 → 81,3 | 7 → 5 | 14 → 10 | 3 → 1 | 93,7 % → 94,0 % | p. 1, 2, 4, 7, 10, 11 / 16 | NOT_STARTED (0/418) | **REVIEW_REQUIRED** |
| DOC-007 | 70,3 → **71,1** [94,4] | 78,7 → 79,2 | 11 → 7 | 21 → 13 | 7 → 3 | 79,6 % → 82,2 % | p. 1, 3 / 5 | NOT_STARTED (0/178) | **REVIEW_REQUIRED** |
| DOC-008 | 66,4 → **68,6** [91,9] | 75,2 → 77,0 | 5 → 4 | 10 → 8 | 2 → 1 | 59,1 % → 68,2 % | p. 1 / 2 | NOT_STARTED (0/74) | **REVIEW_REQUIRED** |
| **Corpus** | 65,9 → **65,7** [90,3] | 74,6 → 73,9 | 55 → 42 | 106 → 80 | 28 → 14 | 85,0 % → 86,1 % | 6/8 docs | NOT_STARTED (0/1 072) | **8 × REVIEW_REQUIRED** |

Lecture : borne basse officielle arrondie vers le bas, borne haute vers le haut. La colonne run27 reproduit exactement le tableau publié en RUN27. Une borne haute ≥ 94 (DOC-003, DOC-006, DOC-007) **n’est pas un seuil atteint** : elle suppose parfaites toutes les inconnues. Le plafond reste à 76,85 (68,52 pour DOC-003, 74,07 pour DOC-005) sans référence humaine. Couverture du corpus pondérée par les caractères.

## 3. Pourquoi la borne basse du corpus baisse (65,9358 → 65,7063, −0,2295)

Écarts exacts par document (règle RUN27, borne basse) : DOC-001 −0,3898 ; DOC-002 0 ; DOC-003 0 ; DOC-004 +0,7805 ; DOC-005 −5,2637 ; DOC-006 +0,0844 ; DOC-007 +0,7750 ; DOC-008 +2,1772. Somme −1,8364, soit −0,2295 sur la moyenne des huit documents.

- **Les deux seules baisses (DOC-001, DOC-005, −0,7067 sur le corpus) viennent de F35.** Les lignes de références conservées en pixels d’origine sont comptées comme « attendues » par la portée gelée `measure_v2.expected_scope`, qui ne connaît pas `reference_line`. Elles passent donc de *written* à *not_attempted*.
  - DOC-005 : couverture 0,2131 → 0,0984. La composante `digit_sequences` passe de 1,0 mesuré à *non applicable*, parce que le seul bloc à chiffres était la ligne dont l’identifiant était altéré en RUN27 (MV-01) et qui n’est plus réécrite. Le plafond baisse de 76,85 à 74,07. `regions_unaltered` monte de 0,984 à 0,995. En RUN27, ce 1,0 récompensait un identifiant devenu faux (gain alors non revendiqué). RUN28 retire ce faux mérite.
  - DOC-001 : couverture 0,5881 → 0,5096, `target_language` 0,835 → 1,0, `no_critical_layout_alert` 0,909 → 0,900.
- **Les six autres documents gagnent +0,4771 sur le corpus** : débordements résolus et pages corrigées (DOC-004, DOC-007), reprise ordinale (DOC-006), recopie partielle supprimée et couverture 0,591 → 0,682 (DOC-008).
- Borne haute : 90,1257 → 90,2433 (+0,1177). Plafond moyen : 75,8102 → 75,4630 (DOC-005).
- **Aucune formule ni portée n’a été modifiée pour compenser** : corriger `expected_scope` exigerait une nouvelle version de méthode (v3) et un recalcul de toutes les comparaisons. Ce n’est pas fait en RUN28 (OI-11).

## 4. Deux comptages critiques à ne pas confondre

| Comptage | Définition | run27 → run28 |
| --- | --- | --- |
| Défauts critiques scorecard-2 | défauts critiques retenus par la mesure v2, **dédoublonnés** par bloc | **55 → 42** |
| Alertes produit `severity=critical` | occurrences d’alertes émises par le produit (une alerte de rendu est émise deux fois par bloc : plan + vérification) | **106 → 80** |

Par code (scorecard-2 / alertes produit) :

| Code | Scorecard-2 run27 → run28 | Alertes produit run27 → run28 |
| --- | --- | --- |
| `LAYOUT_OVERFLOW` | 28 → 14 | 56 → 28 |
| `RENDER_TRANSLATED_TEXT_MISSING` | 6 → 6 | 12 → 12 |
| `RENDER_TEXT_CLIPPED_OR_MISSING` | 6 → 6 | 12 → 12 |
| `RENDER_SOURCE_TEXT_MISSING` | 6 → 6 | 12 → 12 |
| `PROTECTED_REGION_CHANGED` | 6 → 6 | 9 → 9 |
| `SCAN_TEXT_OVER_SOURCE_INK` | 2 → **3** | 4 → **6** |
| `UNMAPPED_TABLE_CONTENT` | 1 → 1 | 1 → 1 |

La hausse de `SCAN_TEXT_OVER_SOURCE_INK` est un **reclassement** du même bloc de DOC-004 (débordement en RUN27, encre résiduelle en RUN28 après F38). Le bloc reste `FAILED` et ses pixels d’origine sont conservés. Toutes les autres familles critiques hors débordement sont **inchangées** : RUN28 ne les a pas corrigées.

## 5. Statuts de blocs (1 072 blocs, transitions exhaustives)

| Transition run27 → run28 | Blocs | Cause |
| --- | --- | --- |
| `FAILED:model_returned_source` → `PRESERVED_INTENTIONALLY:reference_returned_unchanged` | 14 | F35 (retour inchangé légitime) |
| `FAILED:render_overflow` → `TRANSLATED:translated_and_placed` | 10 | F37 |
| `FAILED:model_returned_source` → `PRESERVED_INTENTIONALLY:reference_line` | 9 | F35 (non envoyé) |
| `TRANSLATED:translated_and_placed` → `PRESERVED_INTENTIONALLY:reference_line` | 3 | F35 (dont MV-01) |
| `FAILED:render_overflow` → `FAILED:model_returned_source` | 3 | F40 (cible égale à la source à des marques bidi près) |
| `FAILED:render_overflow` → `FAILED:render_residual_source_ink` | 1 | F38 (reclassement) |
| `FAILED:implausible_target` → `TRANSLATED:translated_and_placed` | 1 | F41 + F42 |

Totaux : `TRANSLATED` 492 → 500, `FAILED` 142 → 108, `PRESERVED_INTENTIONALLY` 147 → 173, `UNCERTAIN` 150 → 150, `NOT_TRANSLATABLE` 141 → 141. Les 3 blocs `TRANSLATED` devenus `reference_line` (un par document : DOC-001, DOC-004, DOC-005) font baisser la couverture mesurée sans perte réelle. Leur « traduction » RUN27 n’ajoutait que des espaces ou un point à la lecture OCR, re-typographiée par-dessus l’original. Pour DOC-005, cette lecture portait l’identifiant altéré (MV-01).

## 6. PDF réellement produits (inspection visuelle privée)

Nombre de pages identique pour 8/8. DOC-002 et DOC-003 sont pixel-identiques à RUN27 (non-régression des documents simples). 27 zones modifiées au-dessus du seuil de 40 niveaux, toutes inspectées sur planches original | RUN27 | RUN28, avec agrandissements ×3.

| Catégorie | Constats vérifiés à l’œil |
| --- | --- |
| Améliorations visibles | DOC-001 : pied de page de références en pixels d’origine. DOC-004 : raison sociale en pixels d’origine ; case de formulaire en pixels d’origine. DOC-005 : lignes adresse et identifiants en pixels d’origine, **identifiant d’origine intact (MV-01 corrigé)**. DOC-006 : libellé de formulaire, ligne de tableau et phrase de dates traduits ; bande grise supprimée. DOC-007 : quatre titres ou libellés traduits, titre sur fond blanc, ligne source résiduelle remplacée (MV-03 corrigé). DOC-008 : pied bilingue sans mots source recopiés. |
| Réserves visibles | Corps condensés très petits (MV-05 : 9 blocs rendus, DOC-004 3, DOC-006 2, DOC-007 4). DOC-004 : une ligne incohérente issue d’un OCR bruité, identique en RUN27 (MV-07, préexistante) ; phrases de droite à gauche traduites ligne à ligne (MV-06). DOC-006 : graisse de la source perdue et jour ordinal sans suffixe français (MV-08). |
| Régression intermédiaire | DOC-004 : case re-typographiée (MV-04), trouvée pendant RUN28 et corrigée par F40 avant le verdict. Absente de run28e. |
| Inchangé | Tampons, cases cochées de DOC-007 (MV-02, corrigé en RUN27), régions protégées. |

## 7. Provenance et appels au modèle

| Exécution | Requêtes Interim | Documents concernés | Réservation max. (≤ 32 768) | Violations de budget |
| --- | --- | --- | --- | --- |
| run28 | 2 | DOC-006, DOC-008 | 16 370 (DOC-006), 16 425 (DOC-008) | 0 |
| run28b | 1 | DOC-006 | 16 295 | 0 |
| run28c | 1 | DOC-006 | 16 295 | 0 |
| run28d | 2 | DOC-006 (passe + reprise F41) | 16 608 | 0 |
| **run28e (verdict)** | **0** | 8 × `TRANSLATION_MEMORY_REUSE_ONLY` | — | 0 |

Total RUN28 : 6 requêtes, toutes sous autorisation privée SHA-listée et expirante, avec garde de 32 768 tokens. Provenance des 1 072 blocs du verdict : 1 058 `TRANSLATION_MEMORY` (correspondances revalidées par les gardes courantes), 14 `NOT_SENT`. Originaux inchangés à chacune des cinq exécutions. `human_reference_validated = false` pour les 8 documents.
