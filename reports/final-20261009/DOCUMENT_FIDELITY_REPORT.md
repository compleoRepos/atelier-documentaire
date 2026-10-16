# Rapport de fidélité documentaire — avant / après (09/10)

## 1. Périmètre et méthode

- **Avant (baseline)** : sorties du passage Interim du 08/10, sauvegardées avant les correctifs (`baseline-617`, privé).
- **Après (final)** : passage **run17**, empreinte du code `f69a6210b29e8196`.
  - Il réutilise l’analyse complète run10, c’est-à-dire l’OCR et l’IR produits par le code final d’OCR et de segmentation.
  - Il envoie de nouvelles requêtes Interim, bornées à 32K, puis reconstruit les PDF candidats.
- **Périmètre** : les 8 PDF originaux autorisés, soit 31 pages, toutes scannées.
- **Mesure** : `tools/recette/measure_corpus_metrics.py`, avec relecture OCR du texte source résiduel et zones visuelles en union baseline ∪ final.
  - Les deux côtés sont mesurés avec le même outil, la même résolution et les mêmes définitions.
- **Rendus comparatifs** : `tools/recette/compare_visual_sheets.py`. Une planche par page présente l’original, l’ancienne traduction, la nouvelle traduction et les différences entre le final et l’original. Une planche par document audite les zones visuelles (cachets, logos, signatures, candidats reclassés).
  - 31 planches de pages et 8 planches d’audit, environ 20 Mo.
  - Elles contiennent des données personnelles. Elles restent dans le répertoire privé (`$PRIVATE/comparisons/run17-vs-baseline/DOC-00x/`) et dans l’archive privée, **jamais dans Git**.
- **Métriques JSON** :
  - Détaillées, privées : `$PRIVATE/metrics/metrics-run17-final.json` et `$PRIVATE/metrics/metrics-baseline-617-run17cmp.json`.
  - Anonymisées, versionnées : `CORPUS_METRICS_FINAL.json`, compteurs uniquement, sans SHA, nom de fichier, chemin ni contenu.

**Statut** : 8/8 documents en `REVIEW_REQUIRED`. Aucune référence humaine n’est validée, et des alertes critiques restent visibles sur 6 documents. Aucun document n’est déclaré PASS.

## 2. Fidélité par document

| Doc | Pages | Lignes OCR | Blocs IR | Résiduel source (mots) | Débordement | Coupé/manquant | Superposition | Masque trop grand | Texte sur encre source (écarté) | Texte protégé non traduit | Visuels préservés / vérifiés | Visuels altérés | Statut |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DOC-001 | 2 | 55 | 41 → 47 | 2 → 0 / 7 | 0 → 1 | 9 → 12 | 1 → 1 | 0 → 0 | 0 → 0 | 3 → 2 | 11/11 → 6/11 | 5 (+0 légers) | REVIEW_REQUIRED |
| DOC-002 | 1 | 37 | 19 → 35 | 3 → 3 / 17 | 0 → 1 | 3 → 15 | 1 → 3 | 0 → 0 | 0 → 1 | 1 → 1 | 4/4 → 4/4 | 0 (+0 légers) | REVIEW_REQUIRED |
| DOC-003 | 1 | 13 | 11 → 13 | NULL → NULL / NULL | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 1/1 → 1/1 | 0 (+0 légers) | REVIEW_REQUIRED |
| DOC-004 | 2 | 243 | 155 → 225 | 49 → 70 / 131 | 4 → 17 | 72 → 108 | 2 → 2 | 2 → 0 | 0 → 6 | 9 → 4 | 3/3 → 2/3 | 0 (+1 léger) | REVIEW_REQUIRED |
| DOC-005 | 2 | 98 | 66 → 96 | NULL → NULL / NULL | 0 → 0 | 12 → 0 | 0 → 0 | 0 → 0 | 0 → 0 | 16 → 3 | 3/3 → 3/3 | 0 (+0 légers) | REVIEW_REQUIRED |
| DOC-006 | 16 | 631 | 538 → 434 | 33 → 16 / 1086 | 0 → 3 | 36 → 18 | 2 → 0 | 12 → 24 | 0 → 1 | 17 → 6 | 19/19 → 13/19 | 5 (+1 léger) | REVIEW_REQUIRED |
| DOC-007 | 5 | 247 | 136 → 222 | 58 → 82 / 397 | 2 → 11 | 54 → 105 | 4 → 7 | 6 → 4 | 0 → 16 | 23 → 2 | 7/7 → 4/7 | 0 (+3 légers) | REVIEW_REQUIRED |
| DOC-008 | 2 | 91 | 75 → 76 | 1 → 0 / 48 | 0 → 2 | 9 → 18 | 1 → 1 | 0 → 0 | 0 → 1 | 13 → 4 | 8/8 → 8/8 | 0 (+0 légers) | REVIEW_REQUIRED |

Lecture du tableau :

- **Lignes OCR.** Le chiffre indiqué est celui de l’IR final. La baseline avait une ligne par bloc (1 041). Le découpage aux grands blancs (D14) porte le total à 1 415 lignes, regroupées en 1 148 blocs (D1).
- **Résiduel source.** Mots source encore lus par l’OCR sur le candidat, rapportés aux mots éligibles relus sur l’original. `NULL` signifie que la mesure n’est pas applicable : DOC-003 et DOC-005 sont en français, donc aucun mot n’est éligible. Ce `NULL` n’est jamais converti en 0 ou en PASS.
- **Coupé/manquant.** Il compte les blocs traduits non retrouvés dans le candidat. Le compteur agrégé `cat:clipped_or_missing` additionne les trois codes `RENDER_*_MISSING`, qui portent ce même compteur : il le compte donc trois fois (§3).
- **Visuels altérés.** Ce sont des zones que la baseline protégeait à tort et que le final traduit volontairement. Il s’agit de lettres colorées d’un titre (DOC-001) et de lignes surlignées (DOC-006), reclassées avec trace (D4, D5). Aucun cachet, logo ni signature réel n’est altéré (§5).

## 3. Totaux (baseline → final)

| Mesure (§15) | Indicateur | Baseline | Final | Lecture |
|---|---|---|---|---|
| Couverture de traduction | `coverage_chars_strict` | 0.8810 | 0.8788 | Stable. Le détail est dans `TRANSLATION_COVERAGE_REPORT.md`. |
| Couverture écrite dans le PDF | `coverage_chars_written_strict` | 0.8305 | 0.8065 | En baisse : les gardes conservent la source plutôt que de superposer ou tronquer. |
| Texte source résiduel | mots relus sur le candidat | 146 / 1 854 | 171 / 1 833 | **Hausse réelle**, due aux sources conservées volontairement et signalées par les gardes (D6/D23, D20, D16, D9). |
| Texte cible manquant (silencieux) | `silent_missing_chars` | 0 | 0 | Aucune perte silencieuse. |
| Texte coupé ou manquant | `cat:clipped_or_missing` (3 codes, même compteur) | 195 | 276 | Voir §4 : en final, 60 des 92 blocs manquants sont écartés par une garde signalée. |
| Débordements | `cat:overflow` | 6 | 35 | Alertes volontaires (D16), avec source conservée et sans troncature silencieuse. |
| Superpositions | `cat:overlap` | 11 | 14 | **Régression légère.** Les cadres agrandis de deux voisins ne sont pas mutuellement exclus (limite 6 de l’audit). |
| Masque trop grand | `cat:mask_too_large` | 20 | 28 | **Régression**, portée par DOC-006 (12 → 24). Masques par ligne sur les lignes surlignées. |
| Texte protégé non traduit | `cat:protected_text_kept` | 82 | 22 | Moins de texte bloqué par de fausses zones protégées (D4, D5). |
| Intégrité des données critiques | `cat:critical_data` | 7 | 4 | Toutes visibles et critiques. Les blocs rejetés par la garde d’entités gardent leur source (D26). |
| Texte sur encre source | `cat:text_over_source_ink` | 0 | 25 | Nouvelle garde D20 : items écartés plutôt que dessinés sur une source non masquée. |
| Cellules rendues bloc par bloc | `cat:table_cell_fallback` | 37 | 38 | Stable. |
| Cohérence des polices | `cat:font_reduced` | 0 | 42 | Réductions tracées (plancher 72 %). Le détail par document est au §6. |
| Conservation des images, cachets, signatures | zones visuelles vérifiées | 56 | 56 | 41 préservées, 10 altérées volontairement (reclassées), 5 légèrement touchées (§5). |

## 4. Texte cible manquant : décomposition

« Blocs traduits non retrouvés » est l’indicateur `missing_block_count` de l’évaluateur. Il vaut le nombre de blocs traduits moins le nombre de blocs retrouvés dans le candidat.

| | Baseline | Final |
|---|---|---|
| Blocs traduits | 670 | 545 (regroupement D1) |
| Blocs retrouvés dans le candidat | 605 | 453 |
| Blocs non retrouvés | 65 | 92 |
| dont écartés par une garde signalée bloc par bloc (`LAYOUT_OVERFLOW`, `SCAN_TEXT_OVER_SOURCE_INK`) | 6 | 60 |
| dont solde non attribuable | 59 | 32 |

Le solde non attribuable baisse de 59 à 32. Ces blocs restent comptés comme non écrits, et l’alerte agrégée `RENDER_*_MISSING` reste critique (limite 12 de l’audit).

## 5. Contrôle visuel par document

Toutes les planches de pages et d’audit des zones visuelles ont été générées. Les documents les plus complexes ont été examinés planche par planche : DOC-001, DOC-004, DOC-006 et DOC-007 sur run17, DOC-005 sur run14 puis vérifié en run17. Les constats ne citent aucun contenu.

| Doc | Type | Constats (final) |
|---|---|---|
| DOC-001 | Attestation scannée avec logos et cachets de signature électronique | 4 marques de logo, 1 pictogramme et 2 cachets de signature électronique **préservés**. Les 5 zones « altérées » sont les lettres colorées du titre, reclassées en texte (D5) et traduites. Le veto multicolore garde le logo voisin protégé. |
| DOC-002 | Lettre d’une page | 4/4 zones visuelles préservées. 1 débordement et 1 item écarté sur encre source, tous deux signalés. |
| DOC-003 | Document français | Aucune traduction attendue. Seuls 3 fragments courts (en-tête, titre, date) sont détectés à tort comme non français (limite 7 de l’audit). Zone visuelle préservée. |
| DOC-004 | Formulaire bilingue en tableau, avec 2 cachets et une signature | Structure du tableau, 2 cachets et signature **préservés**. Les superpositions illisibles de la baseline sur la colonne arabe ont disparu. En contrepartie, davantage de cellules restent en langue source : 17 débordements, 6 items sur encre et des cellules préservées par la garde de structure. La couverture écrite passe de 0.6829 à 0.3748. C’est le principal arbitrage fidélité / couverture du corpus. 1 zone visuelle légèrement touchée. |
| DOC-005 | Document français (formulaire) | Zones visuelles préservées (3/3). Le pied de page surimprimé n’est plus réécrit (D25). Les fragments courts détectés non français sont laissés en source et signalés (limite 14). |
| DOC-006 | Contrat de 16 pages avec surlignages, manuscrit et cachet | Lignes surlignées traduites, surlignage mesuré reproduit (D3, D11). Manuscrit p3, marques p2, noms et dates surlignés, et date sous cachet p4 **préservés**. 1 zone légèrement touchée. Constats à revoir : 12 → 24 masques trop grands, 1 alerte d’unité modifiée (§7), et en pied de page p16 un **nom de fichier imprimé** traduit comme du texte. Ce dernier point est un identifiant non protégé, à ajouter aux limites. |
| DOC-007 | Formulaire administratif de 5 pages | Cadres de formulaire, cases à chiffres et identifiants intacts. Le logo et le graphisme p3 sont communs et intacts. Seuls les libellés et valeurs à l’intérieur des cadres reclassés (D4) sont traduits, ce qui explique les 3 zones « légèrement touchées ». Titres de section sur une ligne (D15, D16). 11 débordements et 16 items écartés sur encre, tous signalés. |
| DOC-008 | Document de 2 pages | 8/8 zones visuelles préservées. Couverture en hausse (0.5703 → 0.7690). 2 débordements et 1 item sur encre, signalés. |

## 6. Cohérence des polices

Pour chaque document : nombre de tailles distinctes / part de la taille modale / taille minimale (pt) / part des caractères sous 7 pt.

| Doc | Baseline | Final |
|---|---|---|
| DOC-001 | 5 / 0.33 / 5.0 / 0.60 | 4 / 0.50 / 4.5 / 0.44 |
| DOC-002 | 2 / 0.55 / 10.0 / 0.00 | 2 / 0.98 / 6.5 / 0.03 |
| DOC-003 | NULL (rien d’écrit) | 2 / 0.85 / 9.0 / 0.00 |
| DOC-004 | 9 / 0.24 / 4.0 / 0.60 | 7 / 0.33 / 4.5 / 0.70 |
| DOC-005 | 2 / 0.98 / 5.0 / 0.02 | 2 / 0.86 / 7.5 / 0.00 |
| DOC-006 | 12 / 0.45 / 5.0 / 0.26 | 13 / 0.78 / 6.0 / 0.01 |
| DOC-007 | 10 / 0.27 / 5.0 / 0.77 | 9 / 0.56 / 4.5 / 0.43 |
| DOC-008 | 6 / 0.62 / 4.0 / 0.22 | 6 / 0.65 / 5.0 / 0.20 |

Le corps de texte est plus homogène (part modale en hausse sur 6 documents) et la part des caractères sous 7 pt baisse fortement sur DOC-006 et DOC-007. Deux réserves :

- DOC-004 voit cette part augmenter (0.60 → 0.70), car les cellules du formulaire bilingue sont étroites.
- Des tailles de 4,5 pt subsistent dans des cellules de formulaire (limite 10 de l’audit).

## 7. Alertes critiques restantes (final)

| Doc | Codes critiques (nombre) |
|---|---|
| DOC-001 | `LAYOUT_OVERFLOW` 1, `RENDER_*_MISSING` (×3 codes), `PDF_TABLE_STRUCTURE_CHANGED` 1 (faux positif probable de l’évaluateur, laissé critique, limite 11) |
| DOC-002 | `PROTECTED_ENTITY_CHANGED` 1, `LAYOUT_OVERFLOW` 1, `SCAN_TEXT_OVER_SOURCE_INK` 1, `RENDER_*_MISSING` (×3) |
| DOC-003 | aucune |
| DOC-004 | `LAYOUT_OVERFLOW` 17, `SCAN_TEXT_OVER_SOURCE_INK` 6, `RENDER_*_MISSING` (×3) |
| DOC-005 | aucune (baseline : `RENDER_*_MISSING` ×3) |
| DOC-006 | `PROTECTED_ENTITY_CHANGED` 1, `HALLUCINATION_UNIT_CHANGED` 1 (unité « m » ×2 absente de la cible, les 4 « % » conservés), `LAYOUT_OVERFLOW` 3, `SCAN_TEXT_OVER_SOURCE_INK` 1, `RENDER_TEXT_MASK_TOO_LARGE` / `VISUAL_MASK_TOO_LARGE` 12, `RENDER_*_MISSING` (×3) |
| DOC-007 | `UNMAPPED_TABLE_CONTENT` 1, `PROTECTED_ENTITY_CHANGED` 1, `LAYOUT_OVERFLOW` 11, `SCAN_TEXT_OVER_SOURCE_INK` 16, `RENDER_TEXT_MASK_TOO_LARGE` / `VISUAL_MASK_TOO_LARGE` 2, `RENDER_*_MISSING` (×3) |
| DOC-008 | `LAYOUT_OVERFLOW` 2, `SCAN_TEXT_OVER_SOURCE_INK` 1, `RENDER_*_MISSING` (×3) |

Disparus par rapport à la baseline :

- `CRITICAL_ENTITY_EXTRA` (2) et `HALLUCINATION_ENTITY_ADDED` (1) sur DOC-001.
- 1 `PROTECTED_ENTITY_CHANGED` sur DOC-007.
- `RENDER_*_MISSING` sur DOC-005.
- Masques trop grands sur DOC-004 (1 → 0).

Pour les 4 blocs DOC-004 rejetés par la garde d’entités, la vérification confirme que la source est conservée et qu’aucune traduction n’est appliquée (D26).

## 8. Conditions d’acceptation (§18) : état

| Condition | État | Preuve |
|---|---|---|
| Les huit documents ont été rejoués | Oui | run17 8/8, `error=null`, SHA des originaux inchangés. Corpus golden : voir `TEST_REPORT.md`. |
| Résultats comparés aux sorties précédentes | Oui | §2 à §7 et planches privées. |
| Défauts corrigés ou documentés | Oui | `AUDIT_CORRECTIFS.md` : D1 à D27 et limites 1 à 18. |
| Tableaux et champs conservent leur structure | Oui, avec réserves | Gardes de structure (D6, D23), cellules rendues bloc par bloc, audit visuel DOC-004/DOC-007. Réserves : 1 `UNMAPPED_TABLE_CONTENT` sur DOC-007, 1 faux positif tableau sur DOC-001. |
| Données critiques protégées | Oui, signalé | 4 alertes critiques visibles. Blocs rejetés conservés en source. Double lecture sous surligneur (D11). |
| Cachets, signatures et logos préservés | Oui | Aucun altéré dans l’audit visuel. Les 10 zones « altérées » sont des candidats reclassés en texte avec trace. |
| Textes manquants et résiduels détectés | Oui | 0 manquant silencieux, résiduel mesuré par OCR, solde non attribuable signalé. |
| Pas de régression des tests | Oui | 549/549 tests techniques et 16/16 tests frontend (`TEST_REPORT.md`). |
| Limites clairement identifiées | Oui | `AUDIT_CORRECTIFS.md` (« Défauts restants et limites ») et ce rapport (nom de fichier en pied de page sur DOC-006, unité « m » sur DOC-006, masques trop grands sur DOC-006, couverture écrite de DOC-004). |
