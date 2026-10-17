# RUN29 — Comparaison avant / après

**Avant** = RUN28 publié (exécution `run28e`). **Après** = RUN29 final (exécution `run29j`, code F43–F53). Tous les chiffres de ce rapport sont recalculables à partir des exports anonymisés [documents/](documents/) ; les tableaux sont générés depuis ces exports, sans copie manuelle.

## 1. Conditions de comparaison

| Condition | Valeur |
|---|---|
| Originaux | les mêmes 8 PDF autorisés (empreintes vérifiées avant et après chaque exécution : inchangées) |
| Traductions Interim | **mémoire** d'inférences réelles passées, revalidée par les gardes actuelles ; **0 requête** en RUN29. Une traduction de mémoire n'est jamais comptée comme nouvelle inférence |
| Méthodes de score | v1 (gel RUN26) et v2 (gel RUN27) : formules, poids, seuils et inconnues **inchangés** ; gels vérifiés par empreinte (12/12) |
| Règles de mesure | RUN28 `08e998169c0dad9b` et RUN29 `4d6b306029f8745b` appliquées aux **mêmes artefacts** : 168 valeurs v1 et 224 valeurs v2 identiques. L'écart ci-dessous vient donc des fichiers produits, pas de la règle |
| Valeur officielle | borne basse v2 ; la borne haute (inconnues comptées au mieux) et le plafond sans référence humaine ne valent jamais validation |
| Références humaines | 0 ligne revue sur 1 072 : le sens n'est pas mesuré |

## 2. Score selon la méthode existante

| Document | v2 RUN28 | v2 RUN29 | Écart (borne basse exacte) | Borne haute RUN29 | Plafond sans humain | v1 RUN28 → RUN29 |
|---|---|---|---|---|---|---|
| DOC-001 | 62,7671 | 60,0160 | -2,7511 | 83,1641 | 76,8519 | 71,7 → 69,4 |
| DOC-002 | 66,7078 | 66,4029 | -0,3050 | 89,5510 | 76,8519 | 75,4 → 75,2 |
| DOC-003 | 62,7058 | 62,7058 | 0 | 94,1873 | 68,5185 | 71,4 → 71,4 |
| DOC-004 | 67,0037 | 65,7223 | -1,2814 | 88,8705 | 76,8519 | 75,8 → 74,6 |
| DOC-005 | 53,0419 | 47,1767 | -5,8652 | 73,1026 | 74,0741 | 59,1 → 56,8 |
| DOC-006 | 73,5820 | 73,5358 | -0,0462 | 96,6839 | 76,8519 | 81,3 → 81,3 |
| DOC-007 | 71,1721 | 71,5603 | +0,3881 | 94,7084 | 76,8519 | 79,2 → 79,5 |
| DOC-008 | 68,6699 | 68,6699 | 0 | 91,8180 | 76,8519 | 77,0 → 77,0 |
| **Corpus** | **65,7063** | **64,4737** | **-1,2326** | 89,0107 | 75,4630 | 73,9 → 73,2 |

**Le score baisse : 65,7063 → 64,4737 (−1,2326) sur le corpus.** La borne haute baisse du même écart (90,2433 → 89,0107) et le plafond est inchangé (75,4630). Le seuil de 94 n'est pas atteint ; il est **inaccessible** sans références humaines puisque le plafond vaut 75,4630.

### 2.1 Pourquoi le score baisse alors que les rendus sont plus sûrs

Le score corpus est la moyenne des 8 documents. Contributions exactes à l'écart : DOC-005 −0,7331, DOC-001 −0,3439, DOC-004 −0,1602, DOC-002 −0,0381, DOC-006 −0,0058, DOC-007 +0,0485, DOC-003 et DOC-008 0.

1. **Refus prudents de traductions visuellement endommagées (F50, F50c, F53).** En RUN28, 14 traductions étaient placées alors que la couverture coupait des glyphes de la source restés visibles à côté (moitiés de mots, chiffres, lettres de tampon, logo) ou que le texte traduit était barré par un filet de tableau. Ces défauts existaient déjà en RUN28 mais **aucune métrique ne les voyait**. RUN29 conserve les pixels d'origine et signale une anomalie critique. La méthode gelée compte cette traduction manquante en couverture : DOC-005 perd son **seul** bloc traduit (couverture écrite 9,8 % → 0 %, et le triplet de vérification du rendu apparaît), DOC-001 perd 1 bloc (51,0 % → 39,6 %), DOC-004 9 blocs, DOC-006 3 blocs.
2. **Nouvelles détections de défauts préexistants (F49, F50).** 5 filets de tableau effacés (`RENDER_RULE_ERASED`) et 12 couvertures coupant des glyphes (`SCAN_COVER_CUTS_SOURCE_GLYPHS`) sont désormais des défauts critiques mesurés.
3. **Gains réels.** 6 lignes autrefois en débordement sont désormais traduites (F44, F45 ; lisibilité à valider humainement) ; les 6 régions protégées modifiées de DOC-004 (cases à cocher) sont restaurées (F43) ; DOC-007 progresse (+0,3881).

Aucune formule, aucun poids ni aucun seuil n'a été modifié pour compenser cette baisse. Elle est le prix mesuré de la décision « ne jamais livrer un rendu qui mutile l'original ».

## 3. Quatre niveaux par document

Borne basse pondérée de chaque niveau, sur les dimensions gelées de la v2 (sans changement de formule) : **sens** = traduction + hallucination ; **intégrité des données** = entités ; **couverture** = couverture ; **format** = mise en page + fidélité à la source. Entre parenthèses, la borne haute RUN29. ▲ / ▼ : hausse / baisse de la borne basse.

| Document | Sens RUN28 → RUN29 | Intégrité des données RUN28 → RUN29 | Couverture RUN28 → RUN29 | Format RUN28 → RUN29 |
|---|---|---|---|---|
| DOC-001 | 0,567 → 0,567 (haut 1,000) | 0,667 → 0,667 (haut 1,000) | 0,510 → 0,396 ▼ (haut 0,396) | 0,865 → 0,855 ▼ (haut 0,855) |
| DOC-002 | 0,564 → 0,567 ▲ (haut 1,000) | 0,667 → 0,667 (haut 1,000) | 0,644 → 0,628 ▼ (haut 0,628) | 0,955 → 0,954 ▼ (haut 0,954) |
| DOC-003 | 0,267 → 0,267 (haut 1,000) | 0,667 → 0,667 (haut 1,000) | 0,741 → 0,741 (haut 0,741) | 0,998 → 0,998 (haut 0,998) |
| DOC-004 | 0,559 → 0,559 (haut 0,992) | 0,667 → 0,667 (haut 1,000) | 0,644 → 0,583 ▼ (haut 0,583) | 0,972 → 0,976 ▲ (haut 0,976) |
| DOC-005 | 0,567 → 0,567 (haut 1,000) | 0,500 → 0,500 (haut 1,000) | 0,098 → 0,000 ▼ (haut 0,000) | 0,999 → 0,833 ▼ (haut 0,833) |
| DOC-006 | 0,566 → 0,566 (haut 0,999) | 0,667 → 0,667 (haut 1,000) | 0,940 → 0,939 ▼ (haut 0,939) | 0,918 → 0,917 ▼ (haut 0,917) |
| DOC-007 | 0,560 → 0,560 (haut 0,994) | 0,667 → 0,667 (haut 1,000) | 0,822 → 0,835 ▲ (haut 0,835) | 0,991 → 0,995 ▲ (haut 0,995) |
| DOC-008 | 0,567 → 0,567 (haut 1,000) | 0,667 → 0,667 (haut 1,000) | 0,682 → 0,682 (haut 0,682) | 0,962 → 0,962 (haut 0,962) |

Lecture :

- **Sens** : inchangé, et non mesurable. Les bornes basses (0,27 à 0,57) reflètent la part inconnue faute de références humaines, pas une qualité constatée.
- **Intégrité des données** : inchangée. Aucune altération d'entité acceptée n'est mesurée ; les gardes d'entités (identifiants, montants, dates) ne sont pas modifiées en RUN29. Cette mesure compare à l'OCR, pas à l'image : elle ne voit pas MV-06, MV-07 ni MV-18 (voir § 7).
- **Couverture** : baisse sur DOC-001, DOC-002, DOC-004, DOC-005 et DOC-006 (refus prudents § 2.1), hausse sur DOC-007 (débordements traduits).
- **Format** : hausse sur DOC-004 et DOC-007 (débordements, cases à cocher), baisse sur DOC-005 (triplet de vérification du rendu lié au refus de son seul bloc traduit).

## 4. Résultats produit par document

| Document | Blocs | Traduits et placés | Défauts critiques sc-2 | Alertes produit critiques | Débordements | Couverture écrite | Statut | Lignes humaines revues |
|---|---|---|---|---|---|---|---|---|
| DOC-001 | 47 | 8 → 7 | 3 → 4 | 6 → 8 | 0 → 0 | 51,0 % → 39,6 % | `REVIEW_REQUIRED` | 0/47 |
| DOC-002 | 24 | 9 → 8 | 4 → 4 | 8 → 8 | 0 → 0 | 64,4 % → 62,8 % | `REVIEW_REQUIRED` | 0/24 |
| DOC-003 | 13 | 2 → 2 | 0 → 0 | 0 → 0 | 0 → 0 | 74,1 % → 74,1 % | `REVIEW_REQUIRED` | 0/13 |
| DOC-004 | 229 | 93 → 87 | 19 → 21 | 35 → 42 | 9 → 6 | 64,4 % → 58,3 % | `REVIEW_REQUIRED` | 0/229 |
| DOC-005 | 89 | 1 → 0 | 0 → 4 | 0 → 8 | 0 → 0 | 9,8 % → 0,0 % | `REVIEW_REQUIRED` | 0/89 |
| DOC-006 | 418 | 271 → 268 | 5 → 11 | 10 → 22 | 1 → 0 | 94,0 % → 93,9 % | `REVIEW_REQUIRED` | 0/418 |
| DOC-007 | 178 | 93 → 95 | 7 → 5 | 13 → 9 | 3 → 1 | 82,2 % → 83,5 % | `REVIEW_REQUIRED` | 0/178 |
| DOC-008 | 74 | 23 → 23 | 4 → 4 | 8 → 8 | 1 → 1 | 68,2 % → 68,2 % | `REVIEW_REQUIRED` | 0/74 |
| **Corpus** | 1072 | 500 → 490 | 42 → 53 | 80 → 105 | 14 → 8 | — | 8/8 `REVIEW_REQUIRED` | 0/1072 |

## 5. Défauts critiques

Deux comptages distincts, à ne pas additionner : les défauts critiques **scorecard-2**, dédoublonnés par bloc et par code, et les **alertes produit** critiques (occurrences émises par le pipeline, souvent deux par bloc : planification et vérification).

| Code | DOC-001 | DOC-002 | DOC-003 | DOC-004 | DOC-005 | DOC-006 | DOC-007 | DOC-008 | Total |
|---|---|---|---|---|---|---|---|---|---|
| `LAYOUT_OVERFLOW` | · | · | · | 9 → 6 | · | 1 → 0 | 3 → 1 | 1 → 1 | 14 → 8 |
| `PROTECTED_REGION_CHANGED` | · | · | · | 6 → 0 | · | · | · | · | 6 → 0 |
| `RENDER_RULE_ERASED` | · | · | · | 0 → 2 | · | 0 → 3 | · | · | 0 → 5 |
| `RENDER_SOURCE_TEXT_MISSING` | 1 → 1 | 1 → 1 | · | 1 → 1 | 0 → 1 | 1 → 1 | 1 → 1 | 1 → 1 | 6 → 7 |
| `RENDER_TEXT_CLIPPED_OR_MISSING` | 1 → 1 | 1 → 1 | · | 1 → 1 | 0 → 1 | 1 → 1 | 1 → 1 | 1 → 1 | 6 → 7 |
| `RENDER_TRANSLATED_TEXT_MISSING` | 1 → 1 | 1 → 1 | · | 1 → 1 | 0 → 1 | 1 → 1 | 1 → 1 | 1 → 1 | 6 → 7 |
| `SCAN_COVER_CUTS_SOURCE_GLYPHS` | 0 → 1 | · | · | 0 → 7 | 0 → 1 | 0 → 3 | · | · | 0 → 12 |
| `SCAN_TEXT_CROSSES_RULE` | · | · | · | 0 → 2 | · | · | · | · | 0 → 2 |
| `SCAN_TEXT_OVER_SOURCE_INK` | · | 1 → 1 | · | 1 → 1 | · | 1 → 2 | · | · | 3 → 4 |
| `UNMAPPED_TABLE_CONTENT` | · | · | · | · | · | · | 1 → 1 | · | 1 → 1 |
| **Total** | 3 → 4 | 4 → 4 | 0 → 0 | 19 → 21 | 0 → 4 | 5 → 11 | 7 → 5 | 4 → 4 | **42 → 53** |

Lecture : 42 − 6 débordements − 6 régions protégées + 12 glyphes coupés + 5 filets effacés + 2 textes barrés + 3 (triplet DOC-005) + 1 (encre résiduelle DOC-006) = **53**. Alertes produit critiques : 80 → 105.

## 6. Statuts des blocs et transitions

| Document | Blocs | `TRANSLATED` | `PRESERVED_INTENTIONALLY` | `NOT_TRANSLATABLE` | `UNCERTAIN` | `FAILED` |
|---|---|---|---|---|---|---|
| DOC-001 | 47 | 8 → 7 | 21 | 10 | 6 | 2 → 3 |
| DOC-002 | 24 | 9 → 8 | 4 | 2 | 4 → 5 | 5 |
| DOC-003 | 13 | 2 | 11 | 0 | 0 | 0 |
| DOC-004 | 229 | 93 → 87 | 15 | 41 | 57 | 23 → 29 |
| DOC-005 | 89 | 1 → 0 | 54 | 25 | 5 | 4 → 5 |
| DOC-006 | 418 | 271 → 268 | 25 | 36 | 44 | 42 → 45 |
| DOC-007 | 178 | 93 → 95 | 10 | 22 | 32 → 33 | 21 → 18 |
| DOC-008 | 74 | 23 | 33 | 5 | 2 | 11 |
| **Corpus** | 1072 | 500 → 490 | 173 | 141 | 150 → 152 | 108 → 116 |

**24 blocs changent de statut ou de motif** ; chaque transition est attribuée à un correctif et a été contrôlée :

| Transition RUN28 → RUN29 | Blocs | Documents |
|---|---|---|
| `TRANSLATED:translated_and_placed` → `FAILED:render_source_glyphs_cut` | 12 | DOC-001 (1), DOC-004 (7), DOC-005 (1), DOC-006 (3) |
| `FAILED:render_overflow` → `TRANSLATED:translated_and_placed` | 6 | DOC-004 (3), DOC-006 (1), DOC-007 (2) |
| `TRANSLATED:translated_and_placed` → `FAILED:render_text_crosses_rule` | 2 | DOC-004 (2) |
| `FAILED:model_returned_source` → `UNCERTAIN:ocr_unreliable` | 1 | DOC-007 (1) |
| `TRANSLATED:translated_and_placed` → `FAILED:render_residual_source_ink` | 1 | DOC-006 (1) |
| `TRANSLATED:translated_and_placed` → `UNCERTAIN:ocr_unreliable` | 1 | DOC-002 (1) |
| `UNCERTAIN:form_structure_ambiguous` → `UNCERTAIN:ocr_unreliable` | 1 | DOC-005 (1) |
| **Total** | **24** | |

| Transition | Correctif | Vérification |
|---|---|---|
| traduit → `render_source_glyphs_cut` (12) | F50, F50c | 12/12 vus sur recadrages : l'original est conservé au lieu de moitiés de mots, chiffres, tampon ou logo coupés |
| `render_overflow` → traduit (6) | F44 (deux lignes réduites), F45 (interligne serré) | placés sans chevauchement ; **lisibilité à valider humainement** (MV-16) |
| traduit → `render_text_crosses_rule` (2) | F53 | les 2 traductions DOC-004 barrées par un filet ; remplacées par l'original intact |
| vers `ocr_unreliable` (3) | F51 | DOC-002 : valeur manuscrite conservée au lieu d'une phrase inventée. DOC-005 et DOC-007 : blocs déjà non traduits, seulement reclassés (contrôle : la règle F51 les retient, la règle RUN28 non) |
| traduit → `render_residual_source_ink` (1) | F48 | DOC-006 : le filet et la ligne d'origine sont préservés au lieu d'être effacés |

Motifs `FAILED` et `UNCERTAIN` du corpus :

| Motif | RUN28 | RUN29 |
|---|---|---|
| `UNCERTAIN:ocr_unreliable` | 137 | 140 |
| `FAILED:model_returned_source` | 84 | 83 |
| `FAILED:render_source_glyphs_cut` | 0 | 12 |
| `UNCERTAIN:form_structure_ambiguous` | 12 | 11 |
| `FAILED:render_overflow` | 14 | 8 |
| `FAILED:render_mask_unsafe` | 4 | 4 |
| `FAILED:render_residual_source_ink` | 3 | 4 |
| `FAILED:render_rtl_shaping_unsupported` | 3 | 3 |
| `FAILED:render_text_crosses_rule` | 0 | 2 |
| `UNCERTAIN:ocr_script_inconsistent` | 1 | 1 |

## 7. Contrôle visuel sur les fichiers produits

Les PDF produits ont été comparés page par page au RUN28 (empreinte des pixels de chaque page) puis **inspectés à l'œil** sur des planches original | RUN28 | RUN29 et des agrandissements (privés, jamais publiés).

| Document | Pages | Pages modifiées au pixel près | Changements visibles vérifiés sur les fichiers produits |
|---|---|---|---|
| DOC-001 | 2 | 2 | chiffres et tampon d'origine conservés au lieu d'une couverture qui les coupait (F50) |
| DOC-002 | 1 | 1 | valeur manuscrite d'origine conservée au lieu d'une phrase inventée (F51) |
| DOC-003 | 1 | aucune | — |
| DOC-004 | 2 | 1, 2 | cases à cocher intactes (F43) ; trois lignes en débordement désormais traduites sur deux lignes (F44, lisibilité à valider) ; un filet de tableau préservé (F48) ; sept lignes source conservées intactes au lieu de moitiés de mots visibles (F50/F50c) ; une traduction à cheval sur deux rangées, dessinée à travers un filet, remplacée par les libellés d'origine intacts (F53) ; un filet conservé et sa ligne d'origine intacte au lieu d'une traduction barrée (F48 + F53) |
| DOC-005 | 2 | 1 | ligne voisine et chiffres d'origine intacts (F50) ; plus aucun bloc traduit |
| DOC-006 | 16 | 1, 2, 8, 12 | tampon pivoté et logo restaurés (F50c) ; lettres d'un tampon restaurées (F50) ; une ligne en débordement désormais traduite (F44) ; un filet et sa ligne source préservés (F48) |
| DOC-007 | 5 | 1, 3 | titre et ligne en débordement désormais traduits (F45, lisibilité à valider) ; page 3 : 12 pixels, écart au plus 39 sur 255, non visible |
| DOC-008 | 2 | aucune | — |

Défauts vérifiés à l'œil (identifiants `MV`) :

| Document | Id | Défaut | Gravité | RUN28 | RUN29 | Statut |
|---|---|---|---|---|---|---|
| DOC-001 | MV-11 | `SOURCE_GLYPHS_CUT_BY_COVER` | critical | 1 | 0 | FIXED_RUN29 (placement refusé, pixels d'origine conservés, anomalie critique explicite) |
| DOC-002 | MV-12 | `HANDWRITTEN_VALUE_TRANSLATED_AS_INVENTED_TEXT` | critical | 1 | 0 | FIXED_RUN29 (bloc incertain, revue humaine, pixels d'origine conservés) |
| DOC-004 | MV-04 | `CHECKBOX_LABEL_RETYPESET_FROM_OCR` | critical | 0 | 0 | FIXED_RUN28 (inchangé en RUN29) |
| DOC-004 | MV-09 | `CHECKBOX_EDGE_COVERED_BY_MASK` | critical | 3 | 0 | FIXED_RUN29 (F43) |
| DOC-004 | MV-10 | `TABLE_RULE_ERASED_UNDER_COVER` | critical | 4 | 2 | PARTIALLY_FIXED_RUN29 (F48/F48b préservent ; les restes sont signalés critiques) |
| DOC-004 | MV-11 | `SOURCE_GLYPHS_CUT_BY_COVER` | critical | 7 | 0 | FIXED_RUN29 (placement refusé, pixels d'origine conservés, anomalie critique explicite) |
| DOC-004 | MV-05 | `CONDENSED_TEXT_VERY_SMALL` | major | non recompté | non recompté | OPEN_HUMAN_LEGIBILITY_CHECK |
| DOC-004 | MV-16 | `TWO_LINE_REDUCED_OR_TIGHT_LEADING` | major | 0 | 3 | OPEN_HUMAN_LEGIBILITY_CHECK |
| DOC-004 | MV-06 | `RTL_SENTENCE_SPLIT_INTO_OCR_LINES` | critical | 5 | non recompté | OPEN_PREEXISTING (non recompté en RUN29) |
| DOC-004 | MV-07 | `NOISY_OCR_LINE_TRANSLATED_INCOHERENT` | major | 1 | non recompté | OPEN_PREEXISTING (non recompté en RUN29) |
| DOC-004 | MV-14 | `TRANSLATION_OVERLAPS_LIST_NUMBER` | major | 1 | 1 | OPEN_PREEXISTING |
| DOC-004 | MV-15 | `BIDI_PUNCTUATION_ORDER_IN_TARGET` | minor | 1 | 1 | OPEN_PREEXISTING |
| DOC-004 | MV-17 | `TRANSLATION_STRUCK_THROUGH_BY_KEPT_RULE` | critical | 1 | 0 | FIXED_RUN29 (F53 : 2/2 vrais cas refusés, original et filet conservés ; 2 cas mineurs ou ambigus non touchés, à valider humainement) |
| DOC-004 | MV-18 | `SIGNATURE_STROKE_READ_AS_TEXT` | critical | 1 | 1 | OPEN_PREEXISTING |
| DOC-005 | MV-01 | `IDENTIFIER_ALTERED_VS_ORIGINAL_IMAGE` | critical | 0 | 0 | FIXED_RUN28 (inchangé en RUN29) |
| DOC-005 | MV-11 | `SOURCE_GLYPHS_CUT_BY_COVER` | critical | 1 | 0 | FIXED_RUN29 (seul bloc traduit du document refusé : couverture 0, original conservé) |
| DOC-006 | MV-10 | `TABLE_RULE_ERASED_UNDER_COVER` | critical | 6 | 3 | PARTIALLY_FIXED_RUN29 (F48 préserve ; les restes sont signalés critiques) |
| DOC-006 | MV-11 | `SOURCE_GLYPHS_CUT_BY_COVER` | critical | 3 | 0 | FIXED_RUN29 (placements refusés, pixels d'origine conservés) |
| DOC-006 | MV-13 | `STAMP_OR_LOGO_PARTIALLY_ERASED_AND_MISTRANSLATED` | critical | 2 | 0 | FIXED_RUN29 (F50c, éléments graphiques restaurés) |
| DOC-006 | MV-16 | `TWO_LINE_REDUCED_OR_TIGHT_LEADING` | major | 0 | 1 | OPEN_HUMAN_LEGIBILITY_CHECK |
| DOC-006 | MV-08 | `TYPOGRAPHY_DETAIL_LOST` | minor | 1 | 1 | OPEN_HUMAN_REVIEW |
| DOC-007 | MV-02 | `CHECKBOX_STATE_LOST` | critical | 0 | 0 | FIXED_RUN27 (inchangé en RUN29) |
| DOC-007 | MV-16 | `TWO_LINE_REDUCED_OR_TIGHT_LEADING` | major | 0 | 2 | OPEN_HUMAN_LEGIBILITY_CHECK |
| DOC-007 | MV-05 | `CONDENSED_TEXT_VERY_SMALL` | major | non recompté | non recompté | OPEN_HUMAN_LEGIBILITY_CHECK |

## 8. Régressions identifiées

| Régression | Documents | Nature | Décision |
|---|---|---|---|
| Traductions retirées de l'écran (14) | DOC-001, DOC-004, DOC-005, DOC-006 | régression de couverture, **voulue** : l'original intact remplace un rendu mutilé | maintenue ; correction géométrique à faire (OI-07) |
| DOC-005 sans aucun bloc traduit | DOC-005 | conséquence du refus ci-dessus (document composé presque entièrement de références et d'identifiants conservés) | maintenue |
| Lignes réduites ou à interligne serré (6) | DOC-004, DOC-006, DOC-007 | lisibilité non garantie | revue humaine obligatoire |
| Score v2 −1,2326 | corpus | effet des deux premières lignes | expliqué, non compensé |

Aucune régression n'a été trouvée sur les 2 documents identiques au pixel près (DOC-003, DOC-008), ni sur les pages non modifiées des autres documents.

## 9. Limites de comparabilité

- Le sens n'est pas comparé : aucune référence humaine, aucune nouvelle inférence Interim (mémoire réutilisée).
- La mesure d'intégrité compare à l'OCR, pas à l'image : les altérations visibles seulement à l'œil (phrases RTL scindées, OCR bruité, trait de signature lu comme du texte) ne sont pas mesurées.
- Les nouveaux contrôles (F49, F50, F53) rendent RUN29 plus sévère que RUN28 sur des défauts que RUN28 ne voyait pas : à score égal, RUN29 cacherait moins de défauts. Les deux règles de mesure donnent pourtant des valeurs identiques, car ces contrôles s'exécutent au moment du rendu et leurs résultats sont lus dans les artefacts.
