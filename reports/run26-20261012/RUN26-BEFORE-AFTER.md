# RUN26 — Avant / après

Tous les chiffres sont recalculés **avec la même méthode** (`measure-v2.1-run18`, `scorecard-1`, `doc-confidence-1`)
à partir des artefacts de chaque run. Les tableaux sont générés depuis les JSON anonymisés de `documents/` : aucun
chiffre n'est saisi à la main.

Runs comparés :

| Libellé | Description |
|---|---|
| `baseline` | référence initiale du 08/10, immuable |
| `run17` | run historique, comparé pour la couverture seulement |
| `run24` | verdict RUN18 |
| `run25` | **run25e, verdict RUN25 = « avant »** |
| `run26a` | run26 intermédiaire : F25, F26, preuves P0, 5 appels Interim |
| `run26` | **run26b, verdict RUN26 = « après »** : + F27, F28. Rejoue la mémoire de run26a, 0 requête |

## 1. Divergences RUN25 résolues

### 1.1 Les deux tableaux RUN25

Les deux tableaux privés de RUN25 ne mesurent pas le même run :

| Tableau privé | Run mesuré | Moment |
|---|---|---|
| `report-tables-run25` | **run25c**, état intermédiaire avant les correctifs F23 et F24 | avant le verdict |
| `report-tables-run25e` | **run25e**, verdict RUN25 | verdict |

Les écarts touchent **seulement DOC-004 et DOC-008**, ainsi que le total :

| Métrique | run25c | run25e | Cause |
|---|---|---|---|
| Couverture écrite DOC-004 | 0,599 | 0,589 | F23 : blocs aux chiffres de droite à gauche (téléphones) passés en `UNCERTAIN` |
| Couverture écrite DOC-008 | 0,640 | 0,591 | F23 : numéros dont les groupes étaient inversés, passés en `UNCERTAIN` |
| Tentés / écrits DOC-004 (car.) | 2 962 / 2 059 | 2 927 / 2 024 | idem |
| Tentés / écrits DOC-008 (car.) | 1 342 / 1 114 | 1 257 / 1 029 | idem |
| Statuts DOC-004 (traduits / incertains) | 87 / 45 | 86 / 46 | idem |
| Statuts DOC-008 (traduits / incertains) | 23 / 1 | 22 / 2 | idem |
| Catégorie `form_structure_ambiguous` | présente | ventilée sous `ocr_unreliable` | présentation du tableau |
| Couverture écrite du corpus | 0,845 | 0,842 | somme des deux écarts |

Les caractères attendus, partiels et absents sont identiques dans les deux tableaux. Seuls les caractères tentés et
écrits baissent, de 35 pour DOC-004 et de 85 pour DOC-008, du fait des blocs passés en `UNCERTAIN`.

**Les rapports RUN25 versionnés citent bien run25e** (DOC-004 0,589 ; DOC-008 0,591). La mesure v2.1 recalculée en
RUN26 donne la même chose : corpus 0,8419, DOC-004 0,5889, DOC-008 0,5910. **Source de vérité RUN26 : run25e mesuré
en v2.1.**

### 1.2 Résumés de génération et requêtes réelles

Le résumé de run25e indiquait `requests_sent = 0` et aucun modèle servi. Mais sa télémétrie affichait toujours le
fournisseur Interim et le modèle `gpt-5-mini`, car c'est la configuration du moteur, et aucune origine n'était attachée
aux blocs. Un lecteur pouvait donc croire à une nouvelle génération. RUN26 rend cette distinction explicite :

| Document | Mode de génération (verdict) | Requêtes | Provenance des blocs | Original inchangé | Violations budget |
|---|---|---|---|---|---|
| DOC-001 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 47 | oui | 0 |
| DOC-002 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 24 | oui | 0 |
| DOC-003 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 13 | oui | 0 |
| DOC-004 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 229 | oui | 0 |
| DOC-005 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 89 | oui | 0 |
| DOC-006 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 418 | oui | 0 |
| DOC-007 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 178 | oui | 0 |
| DOC-008 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 74 | oui | 0 |

Le run intermédiaire run26a a réellement appelé Interim :

| Document | Requêtes | Réservation max (tokens) | Usage max (tokens) | Violations | Mode |
|---|---|---|---|---|---|
| DOC-001 | 1 | 16 242 | 252 | 0 | `MIXED_MEMORY_AND_NEW_GENERATION` |
| DOC-004 | 2 | 17 379 | 801 | 0 | `MIXED_MEMORY_AND_NEW_GENERATION` |
| DOC-007 | 1 | 16 219 | 246 | 0 | `MIXED_MEMORY_AND_NEW_GENERATION` |
| DOC-008 | 1 | 16 225 | 249 | 0 | `MIXED_MEMORY_AND_NEW_GENERATION` |
| Autres | 0 | — | — | 0 | `TRANSLATION_MEMORY_REUSE_ONLY` |

Provenance des blocs de run26a : 18 `MODEL_CALL`, 973 `TRANSLATION_MEMORY`, 81 `NOT_SENT`, soit 1 072 blocs. Chaque
trace de requête porte un identifiant de corrélation et un identifiant de réponse, et le nombre de traces est égal à
`requests_sent`. Dans le verdict run26b, les 1 072 blocs viennent de la mémoire, **et c'est déclaré** : un bloc obtenu
par appel au modèle en run26a apparaît en run26b comme `TRANSLATION_MEMORY` avec `cached_origin = MODEL_CALL`.

## 2. Scores

| Document | baseline | run24 | run25 | run26a | run26 | Δ run25e → run26 |
|---|---|---|---|---|---|---|
| DOC-001 | 68,3 [84,1] | 65,8 [81,6] | 65,8 [81,6] | 72,0 [87,9] | 72,0 [87,9] | +6,2 |
| DOC-002 | 64,2 [80,0] | 64,8 [80,7] | 64,8 [80,7] | 70,6 [86,4] | 70,6 [86,4] | +5,8 |
| DOC-003 | 25,7 [65,7] | 65,7 [89,1] | 65,7 [89,1] | 71,4 [94,8] | 71,4 [94,8] | +5,7 |
| DOC-004 | 70,7 [86,6] | 67,5 [83,4] | 68,6 [84,4] | 74,5 [90,4] | 74,5 [90,4] | +5,9 |
| DOC-005 | 58,2 [74,0] | 61,6 [77,4] | 61,6 [77,4] | 67,3 [83,1] | 67,3 [83,1] | +5,7 |
| DOC-006 | 76,6 [92,4] | 75,5 [91,3] | 75,5 [91,3] | 81,2 [97,0] | 81,2 [97,0] | +5,7 |
| DOC-007 | 72,4 [88,3] | 72,2 [88,0] | 72,5 [88,3] | 78,1 [93,9] | 78,1 [93,9] | +5,6 |
| DOC-008 | 68,8 [84,6] | 70,4 [86,2] | 69,4 [85,3] | 75,2 [91,1] | 75,2 [91,1] | +5,8 |
| **Corpus** | **63,1** [82,0] | **67,9** [84,7] | **68,0** [84,8] | **73,8** [90,6] | **73,8** [90,6] | **+5,8** |

`run26a` et `run26` ont exactement les mêmes dimensions, défauts et statuts. Seul le nombre de requêtes diffère
(5 → 0). F27 et F28 corrigent des compteurs et des statuts internes, sans effet sur le score.

### 2.1 D'où vient le gain

| Dimension (poids) | run25e (points) | run26 (points) | Δ (points) |
|---|---|---|---|
| Couverture (20) | 12,64 | 12,62 | -0,02 |
| Traduction (15) | 6,36 | 6,37 | +0,01 |
| Fidélité source (10) | 9,37 | 9,37 | +0,00 |
| Entités (15) | 14,38 | 14,38 | +0,00 |
| Mise en page (10) | 9,99 | 9,99 | -0,00 |
| OCR (10) | 4,39 | 4,42 | +0,04 |
| Hallucination (10) | 6,58 | 6,65 | +0,07 |
| Preuves (10) | 4,29 | 10,00 | +5,71 |
| **Total (score officiel)** | **67,99** | **73,80** | **+5,81** |

### 2.2 Dimensions par document (run25e puis run26)

Lecture : une valeur seule est mesurée ; une plage `min–max` contient une part inconnue (sous-composante sans
référence humaine) ; `n/a` = non applicable.

| Document | Run | Couverture (20) | Traduction (15) | Fidélité source (10) | Entités (15) | Mise en page (10) | OCR (10) | Hallucination (10) | Preuves (10) |
|---|---|---|---|---|---|---|---|---|---|
| DOC-001 | run25 | 0,576 | 0,420–0,920 | 0,750 | 1,000 | 1,000 | 0,483–0,983 | 0,632–0,965 | 0,429 |
| DOC-001 | run26 | 0,588 | 0,418–0,918 | 0,750 | 1,000 | 1,000 | 0,483–0,983 | 0,667–1,000 | 1,000 |
| DOC-002 | run25 | 0,393 | 0,500–1,000 | 0,969 | 1,000 | 1,000 | 0,395–0,895 | 0,657–0,990 | 0,429 |
| DOC-002 | run26 | 0,393 | 0,500–1,000 | 0,969 | 1,000 | 1,000 | 0,395–0,895 | 0,657–0,990 | 1,000 |
| DOC-003 | run25 | 0,741 | 0,000–1,000 | 0,995 | 1,000 | 1,000 | 0,500–1,000 | 0,667–1,000 | 0,429 |
| DOC-003 | run26 | 0,741 | 0,000–1,000 | 0,995 | 1,000 | 1,000 | 0,500–1,000 | 0,667–1,000 | 1,000 |
| DOC-004 | run25 | 0,589 | 0,485–0,985 | 0,998 | 1,000 | 0,995 | 0,377–0,877 | 0,652–0,985 | 0,429 |
| DOC-004 | run26 | 0,580 | 0,489–0,989 | 0,998 | 1,000 | 0,996 | 0,401–0,901 | 0,665–0,998 | 1,000 |
| DOC-005 | run25 | 0,454 | 0,500–1,000 | 0,994 | 0,667 | 1,000 | 0,413–0,913 | 0,667–1,000 | 0,429 |
| DOC-005 | run26 | 0,454 | 0,500–1,000 | 0,994 | 0,667 | 1,000 | 0,413–0,913 | 0,667–1,000 | 1,000 |
| DOC-006 | run25 | 0,937 | 0,500–1,000 | 0,842 | 1,000 | 0,998 | 0,493–0,993 | 0,666–0,999 | 0,429 |
| DOC-006 | run26 | 0,937 | 0,500–1,000 | 0,842 | 1,000 | 0,998 | 0,493–0,993 | 0,666–0,999 | 1,000 |
| DOC-007 | run25 | 0,778 | 0,489–0,989 | 0,998 | 1,000 | 0,995 | 0,379–0,879 | 0,660–0,993 | 0,429 |
| DOC-007 | run26 | 0,766 | 0,490–0,990 | 0,999 | 1,000 | 0,995 | 0,380–0,880 | 0,666–0,999 | 1,000 |
| DOC-008 | run25 | 0,591 | 0,500–1,000 | 0,949 | 1,000 | 1,000 | 0,472–0,972 | 0,663–0,996 | 0,429 |
| DOC-008 | run26 | 0,591 | 0,500–1,000 | 0,949 | 1,000 | 1,000 | 0,476–0,976 | 0,667–1,000 | 1,000 |

## 3. Couverture textuelle

### 3.1 Corpus

| Run | Attendus | Tentés | Écrits | Partiels | Absents | Non tentés | Écrits / attendus |
|---|---|---|---|---|---|---|---|
| baseline | 43 085 | 38 597 | 36 039 | 216 | 2 342 | 4 488 | 0,8365 |
| run17 | 42 652 | 38 588 | 34 955 | 292 | 3 341 | 4 064 | 0,8195 |
| run24 | 42 967 | 39 007 | 35 939 | 226 | 2 842 | 3 960 | 0,8364 |
| run25 | 42 967 | 38 773 | 36 173 | 226 | 2 374 | 4 194 | 0,8419 |
| run26a | 43 097 | 38 772 | 36 118 | 226 | 2 428 | 4 325 | 0,8381 |
| run26 | 43 097 | 38 772 | 36 118 | 226 | 2 428 | 4 325 | 0,8381 |

Le nombre de caractères attendus varie d'un run à l'autre, parce que le texte source des scans est celui de l'OCR
du run. La règle de périmètre, elle, est la même (voir [méthodologie](RUN26-SCORE-METHODOLOGY.md) §9.3). En run26,
F25 relit 16 lignes OCR : +112 caractères attendus pour DOC-004, +18 pour DOC-001.

Pertes de run26 par raison, sur le corpus, en caractères :

| Raison | run25e | run26 |
|---|---|---|
| Non tenté : modèle a renvoyé la source (`model_returned_source`) | 2 456 | 1 933 |
| Non tenté : OCR non fiable (`ocr_unreliable`) | 525 | 1 203 |
| Non tenté : structure de formulaire ambiguë | 709 | 709 |
| Non tenté : entité protégée rejetée | 420 | 420 |
| Non tenté : élément visuel protégé | 56 | 56 |
| Non tenté : écriture OCR incohérente | 28 | 4 |
| Absent : débordement de rendu | 1 130 | 1 168 |
| Absent : encre source résiduelle | 860 | 892 |
| Absent : mise en forme de droite à gauche non prise en charge | 170 | 170 |
| Absent : masque non sûr | 104 | 88 |
| Partiel ou absent alors que le bloc est traduit | 226 + 73 | 226 + 73 |
| Absent : élément visuel protégé | 37 | 37 |

### 3.2 Par document

| Document | Run | Attendus | Tentés | Écrits | Partiels | Absents | Non tentés | Écrits / attendus |
|---|---|---|---|---|---|---|---|---|
| DOC-001 | baseline | 627 | 397 | 375 | 0 | 22 | 230 | 0,5981 |
| DOC-001 | run24 | 606 | 442 | 349 | 0 | 93 | 164 | 0,5759 |
| DOC-001 | run25 | 606 | 442 | 349 | 0 | 93 | 164 | 0,5759 |
| DOC-001 | run26 | 624 | 460 | 367 | 0 | 93 | 164 | 0,5881 |
| DOC-002 | baseline | 855 | 519 | 371 | 15 | 133 | 336 | 0,4339 |
| DOC-002 | run24 | 820 | 455 | 322 | 0 | 133 | 365 | 0,3927 |
| DOC-002 | run25 | 820 | 455 | 322 | 0 | 133 | 365 | 0,3927 |
| DOC-002 | run26 | 820 | 455 | 322 | 0 | 133 | 365 | 0,3927 |
| DOC-003 | baseline | 36 | 0 | 0 | 0 | 0 | 36 | 0,0000 |
| DOC-003 | run24 | 81 | 60 | 60 | 0 | 0 | 21 | 0,7407 |
| DOC-003 | run25 | 81 | 60 | 60 | 0 | 0 | 21 | 0,7407 |
| DOC-003 | run26 | 81 | 60 | 60 | 0 | 0 | 21 | 0,7407 |
| DOC-004 | baseline | 3 641 | 3 164 | 2 610 | 0 | 554 | 477 | 0,7168 |
| DOC-004 | run24 | 3 437 | 2 962 | 1 849 | 99 | 1 014 | 475 | 0,5380 |
| DOC-004 | run25 | 3 437 | 2 927 | 2 024 | 99 | 804 | 510 | 0,5889 |
| DOC-004 | run26 | 3 549 | 3 015 | 2 058 | 99 | 858 | 534 | 0,5799 |
| DOC-005 | baseline | 270 | 188 | 12 | 0 | 176 | 82 | 0,0444 |
| DOC-005 | run24 | 366 | 254 | 166 | 0 | 88 | 112 | 0,4536 |
| DOC-005 | run25 | 366 | 254 | 166 | 0 | 88 | 112 | 0,4536 |
| DOC-005 | run26 | 366 | 254 | 166 | 0 | 88 | 112 | 0,4536 |
| DOC-006 | baseline | 26 710 | 24 994 | 24 386 | 44 | 564 | 1 716 | 0,9130 |
| DOC-006 | run24 | 26 942 | 25 448 | 25 235 | 45 | 168 | 1 494 | 0,9366 |
| DOC-006 | run25 | 26 942 | 25 448 | 25 242 | 45 | 161 | 1 494 | 0,9369 |
| DOC-006 | run26 | 26 942 | 25 448 | 25 242 | 45 | 161 | 1 494 | 0,9369 |
| DOC-007 | baseline | 9 206 | 8 309 | 7 333 | 157 | 819 | 897 | 0,7965 |
| DOC-007 | run24 | 8 974 | 8 044 | 6 844 | 82 | 1 118 | 930 | 0,7626 |
| DOC-007 | run25 | 8 974 | 7 930 | 6 981 | 82 | 867 | 1 044 | 0,7779 |
| DOC-007 | run26 | 8 974 | 7 823 | 6 874 | 82 | 867 | 1 151 | 0,7660 |
| DOC-008 | baseline | 1 740 | 1 026 | 952 | 0 | 74 | 714 | 0,5471 |
| DOC-008 | run24 | 1 741 | 1 342 | 1 114 | 0 | 228 | 399 | 0,6399 |
| DOC-008 | run25 | 1 741 | 1 257 | 1 029 | 0 | 228 | 484 | 0,5910 |
| DOC-008 | run26 | 1 741 | 1 257 | 1 029 | 0 | 228 | 484 | 0,5910 |

## 4. Statuts de blocs

| Document | Run | Traduits | Échoués | Incertains | Préservés volontairement | Non traduisibles | Non traités |
|---|---|---|---|---|---|---|---|
| DOC-001 | run25 | 8 | 7 | 1 | 21 | 10 | 0 |
| DOC-001 | run26 | 9 | 3 | 6 | 19 | 10 | 0 |
| DOC-002 | run25 | 8 | 9 | 2 | 3 | 2 | 0 |
| DOC-002 | run26 | 8 | 7 | 4 | 3 | 2 | 0 |
| DOC-003 | run25 | 2 | 1 | 0 | 10 | 0 | 0 |
| DOC-003 | run26 | 2 | 1 | 0 | 10 | 0 | 0 |
| DOC-004 | run25 | 86 | 41 | 46 | 15 | 41 | 0 |
| DOC-004 | run26 | 88 | 33 | 56 | 11 | 41 | 0 |
| DOC-005 | run25 | 3 | 7 | 4 | 50 | 25 | 0 |
| DOC-005 | run26 | 3 | 6 | 5 | 50 | 25 | 0 |
| DOC-006 | run25 | 268 | 63 | 26 | 25 | 36 | 0 |
| DOC-006 | run26 | 268 | 51 | 44 | 19 | 36 | 0 |
| DOC-007 | run25 | 93 | 41 | 12 | 10 | 22 | 0 |
| DOC-007 | run26 | 87 | 32 | 29 | 8 | 22 | 0 |
| DOC-008 | run25 | 22 | 18 | 2 | 27 | 5 | 0 |
| DOC-008 | run26 | 22 | 18 | 2 | 27 | 5 | 0 |
| **Corpus** | run25 | **490** | **187** | **93** | **161** | **141** | **0** |
| **Corpus** | run26 | **487** | **151** | **146** | **147** | **141** | **0** |

### 4.1 Transitions bloc par bloc (run25e → run26)

| Document | Blocs comparés | Inchangés | Transitions de statut run25e → run26 |
|---|---|---|---|
| DOC-001 | 47 | 41 | FAILED->UNCERTAIN ×4, PRESERVED->TRANSLATED ×1, PRESERVED->UNCERTAIN ×1 |
| DOC-002 | 24 | 22 | FAILED->UNCERTAIN ×2 |
| DOC-003 | 13 | 13 | aucune |
| DOC-004 | 229 | 210 | FAILED->NOT_TRANSLATABLE ×1, FAILED->PRESERVED ×1, FAILED->TRANSLATED ×2, FAILED->UNCERTAIN ×6, NOT_TRANSLATABLE->TRANSLATED ×1, PRESERVED->TRANSLATED ×2, PRESERVED->UNCERTAIN ×3, TRANSLATED->FAILED ×2, TRANSLATED->UNCERTAIN ×1 |
| DOC-005 | 89 | 88 | FAILED->UNCERTAIN ×1 |
| DOC-006 | 418 | 399 | FAILED->UNCERTAIN ×12, PRESERVED->TRANSLATED ×1, PRESERVED->UNCERTAIN ×6 |
| DOC-007 | 178 | 160 | FAILED->UNCERTAIN ×10, PRESERVED->UNCERTAIN ×2, TRANSLATED->FAILED ×1, TRANSLATED->UNCERTAIN ×5 |
| DOC-008 | 74 | 74 | aucune |

Lecture :

- **35 blocs `FAILED` → `UNCERTAIN`** et 12 `PRESERVED` → `UNCERTAIN` : leur OCR est non fiable. Ils vont désormais en
  revue humaine pour cette raison réelle, au lieu d'un échec générique ou d'une préservation.
- **6 blocs `TRANSLATED` → `UNCERTAIN`** (DOC-004 ×1, DOC-007 ×5) : leur source OCR a une confiance inférieure à 0,60
  et n'a pas pu être relue de façon sûre. Les traduire, c'était traduire un texte incertain.
- **2 blocs `TRANSLATED` → `FAILED` dans DOC-004** : en run25e, ils étaient traduits depuis une lecture OCR de
  confiance 0,19 et 0,24, donc des faux succès. F25 les relit (confiance 0,94 et 0,91). Le modèle renvoie la nouvelle
  lecture inchangée (`MODEL_CALL`, résultat `UNCHANGED`), d'où `FAILED:model_returned_source` et une revue humaine.
- **1 bloc `TRANSLATED` → `FAILED` dans DOC-007** : c'est une **perte collatérale réelle**, voir §6 et les
  [défauts ouverts](RUN26-OPEN-ISSUES.md).
- **7 blocs deviennent `TRANSLATED`**. Ils étaient auparavant : `PRESERVED` comme nom propre ou référence (×2),
  identique en français (×1), identifiant réécrit (×1, correction F28), `FAILED:model_returned_source` (×2) et
  `NOT_TRANSLATABLE` (×1).
- **2 blocs `FAILED` → non traduits dans DOC-004** (`PRESERVED_INTENTIONALLY: proper_name_or_reference` et
  `NOT_TRANSLATABLE: no_linguistic_content`) : anciens échecs `model_returned_source` sur du bruit OCR (confiance 0,31
  et 0,14), relus par F25 (0,945 et 0,94). L'un est une référence, l'autre une valeur purement numérique. Le
  reclassement découle d'une lecture correcte, ce n'est pas un masquage.

### 4.2 Raisons des statuts (run26)

| Document | Raisons des statuts run26 (blocs) |
|---|---|
| DOC-001 | FAILED:model_returned_source 2, FAILED:render_rtl_shaping_unsupported 1, NOT_TRANSLATABLE:no_linguistic_content 10, PRESERVED_INTENTIONALLY:already_french 9, PRESERVED_INTENTIONALLY:identical_in_french 1, PRESERVED_INTENTIONALLY:identifier_or_number 1, PRESERVED_INTENTIONALLY:proper_name_or_reference 6, PRESERVED_INTENTIONALLY:protected_visual_element 2, TRANSLATED:translated_and_placed 9, UNCERTAIN:form_structure_ambiguous 1, UNCERTAIN:ocr_unreliable 5 |
| DOC-002 | FAILED:entity_guard_rejected 1, FAILED:model_returned_source 5, FAILED:render_residual_source_ink 1, NOT_TRANSLATABLE:no_linguistic_content 2, PRESERVED_INTENTIONALLY:already_french 1, PRESERVED_INTENTIONALLY:proper_name_or_reference 1, PRESERVED_INTENTIONALLY:protected_visual_element 1, TRANSLATED:translated_and_placed 8, UNCERTAIN:ocr_unreliable 4 |
| DOC-003 | FAILED:model_returned_source 1, PRESERVED_INTENTIONALLY:already_french 9, PRESERVED_INTENTIONALLY:identical_in_french 1, TRANSLATED:translated_and_placed 2 |
| DOC-004 | FAILED:model_returned_source 11, FAILED:render_mask_unsafe 1, FAILED:render_overflow 17, FAILED:render_residual_source_ink 3, FAILED:render_rtl_shaping_unsupported 1, NOT_TRANSLATABLE:no_linguistic_content 41, PRESERVED_INTENTIONALLY:already_french 2, PRESERVED_INTENTIONALLY:identifier_or_number 1, PRESERVED_INTENTIONALLY:proper_name_or_reference 4, PRESERVED_INTENTIONALLY:protected_visual_element 4, TRANSLATED:translated_and_placed 88, UNCERTAIN:ocr_unreliable 56 |
| DOC-005 | FAILED:model_returned_source 5, FAILED:render_residual_source_ink 1, NOT_TRANSLATABLE:no_linguistic_content 25, PRESERVED_INTENTIONALLY:already_french 47, PRESERVED_INTENTIONALLY:identical_in_french 1, PRESERVED_INTENTIONALLY:identifier_or_number 2, TRANSLATED:translated_and_placed 3, UNCERTAIN:form_structure_ambiguous 2, UNCERTAIN:ocr_unreliable 3 |
| DOC-006 | FAILED:entity_guard_rejected 1, FAILED:model_returned_source 43, FAILED:render_mask_unsafe 2, FAILED:render_overflow 3, FAILED:render_residual_source_ink 1, FAILED:render_rtl_shaping_unsupported 1, NOT_TRANSLATABLE:no_linguistic_content 36, PRESERVED_INTENTIONALLY:already_french 2, PRESERVED_INTENTIONALLY:identical_in_french 10, PRESERVED_INTENTIONALLY:identifier_or_number 1, PRESERVED_INTENTIONALLY:proper_name_or_reference 1, PRESERVED_INTENTIONALLY:protected_visual_element 5, TRANSLATED:translated_and_placed 268, UNCERTAIN:form_structure_ambiguous 6, UNCERTAIN:ocr_unreliable 38 |
| DOC-007 | FAILED:entity_guard_rejected 1, FAILED:model_returned_source 20, FAILED:render_overflow 7, FAILED:render_residual_source_ink 4, NOT_TRANSLATABLE:no_linguistic_content 22, PRESERVED_INTENTIONALLY:already_french 1, PRESERVED_INTENTIONALLY:identical_in_french 3, PRESERVED_INTENTIONALLY:proper_name_or_reference 3, PRESERVED_INTENTIONALLY:protected_visual_element 1, TRANSLATED:translated_and_placed 87, UNCERTAIN:form_structure_ambiguous 3, UNCERTAIN:ocr_script_inconsistent 1, UNCERTAIN:ocr_unreliable 25 |
| DOC-008 | FAILED:model_returned_source 15, FAILED:render_mask_unsafe 1, FAILED:render_overflow 2, NOT_TRANSLATABLE:no_linguistic_content 5, PRESERVED_INTENTIONALLY:already_french 22, PRESERVED_INTENTIONALLY:identical_in_french 1, PRESERVED_INTENTIONALLY:proper_name_or_reference 1, PRESERVED_INTENTIONALLY:protected_visual_element 3, TRANSLATED:translated_and_placed 22, UNCERTAIN:ocr_unreliable 2 |

## 5. Défauts critiques, entités, mise en page, OCR

### 5.1 Défauts critiques

| Document | Défauts critiques run25e | Défauts critiques run26 |
|---|---|---|
| DOC-001 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 | `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 |
| DOC-002 | `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 | `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 |
| DOC-003 | aucun | aucun |
| DOC-004 | `LAYOUT_OVERFLOW` ×14, `PROTECTED_REGION_CHANGED` ×8, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `VISUAL_MASK_TOO_LARGE` ×1 | `LAYOUT_OVERFLOW` ×17, `PROTECTED_REGION_CHANGED` ×6, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `VISUAL_MASK_TOO_LARGE` ×1 |
| DOC-005 | `ENTITY_DIGITS_MISMATCH` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 | `ENTITY_DIGITS_MISMATCH` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 |
| DOC-006 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1, `HALLUCINATION_UNIT_CHANGED` ×1, `LAYOUT_OVERFLOW` ×3, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×12, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1, `VISUAL_MASK_TOO_LARGE` ×12 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1, `HALLUCINATION_UNIT_CHANGED` ×1, `LAYOUT_OVERFLOW` ×3, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×12, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1, `VISUAL_MASK_TOO_LARGE` ×12 |
| DOC-007 | `LAYOUT_OVERFLOW` ×8, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×2, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `UNMAPPED_TABLE_CONTENT` ×1, `VISUAL_MASK_TOO_LARGE` ×2 | `LAYOUT_OVERFLOW` ×7, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×2, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×4, `UNMAPPED_TABLE_CONTENT` ×1, `VISUAL_MASK_TOO_LARGE` ×2 |
| DOC-008 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 |

Variations run25e → run26 :

- DOC-001 : `LAYOUT_OVERFLOW` 2 → 0.
- DOC-004 : `LAYOUT_OVERFLOW` 14 → 17, et `PROTECTED_REGION_CHANGED` 8 → 6. Les 3 débordements nouveaux sont trois
  blocs relus par F25 : confiance OCR de 0,16–0,29 en run25e, puis de 0,89–0,93. En run25e, le modèle renvoyait la
  lecture erronée inchangée (`FAILED:model_returned_source`). En run26, la bonne lecture est traduite, mais la cible ne
  tient pas dans le cadre (`FAILED:render_overflow`). Ces blocs étaient en échec et le restent, pour une autre cause.
- DOC-007 : `LAYOUT_OVERFLOW` 8 → 7 ; `SCAN_TEXT_OVER_SOURCE_INK` 3 → 4 (le bloc décrit au §6).
- Les 5 autres documents n'ont aucune variation.

### 5.2 Entités protégées

| Document | Blocs traduits avec nombres | Suites de nombres identiques | Défauts d'entité run25e | Défauts d'entité run26 | Noms et clauses |
|---|---|---|---|---|---|
| DOC-001 | 5 | 1,000 | aucun | aucun | inconnu (pas de référence) |
| DOC-002 | 5 | 1,000 | `PROTECTED_ENTITY_CHANGED` ×1 | `PROTECTED_ENTITY_CHANGED` ×1 | inconnu (pas de référence) |
| DOC-003 | 2 | 1,000 | aucun | aucun | inconnu (pas de référence) |
| DOC-004 | 26 | 1,000 | aucun | aucun | inconnu (pas de référence) |
| DOC-005 | 3 | 0,667 | `ENTITY_DIGITS_MISMATCH` ×1 | `ENTITY_DIGITS_MISMATCH` ×1 | inconnu (pas de référence) |
| DOC-006 | 102 | 1,000 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1, `HALLUCINATION_UNIT_CHANGED` ×1, `PROTECTED_ENTITY_CHANGED` ×1 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1, `HALLUCINATION_UNIT_CHANGED` ×1, `PROTECTED_ENTITY_CHANGED` ×1 | inconnu (pas de référence) |
| DOC-007 | 21 | 1,000 | `PROTECTED_ENTITY_CHANGED` ×1 | `PROTECTED_ENTITY_CHANGED` ×1 | inconnu (pas de référence) |
| DOC-008 | 8 | 1,000 | aucun | aucun | inconnu (pas de référence) |

### 5.3 Mise en page mesurée dans le PDF (run26)

| Document | Blocs écrits | Absents | Partiels | Sur encre | Mots insérés | Collisions | Hors page | Défauts critiques de mise en page run26 |
|---|---|---|---|---|---|---|---|---|
| DOC-001 | 9 | 2 | 0 | 0 | 68 | 0 | 0 | `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 |
| DOC-002 | 8 | 1 | 0 | 0 | 56 | 0 | 0 | `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 |
| DOC-003 | 2 | 0 | 0 | 0 | 10 | 0 | 0 | aucun |
| DOC-004 | 83 | 28 | 1 | 1 | 466 | 0 | 0 | `LAYOUT_OVERFLOW` ×17, `PROTECTED_REGION_CHANGED` ×6, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `VISUAL_MASK_TOO_LARGE` ×1 |
| DOC-005 | 3 | 1 | 0 | 0 | 34 | 0 | 0 | `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 |
| DOC-006 | 264 | 11 | 2 | 0 | 4692 | 0 | 0 | `LAYOUT_OVERFLOW` ×3, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×12, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1, `VISUAL_MASK_TOO_LARGE` ×12 |
| DOC-007 | 85 | 11 | 2 | 0 | 1076 | 0 | 0 | `LAYOUT_OVERFLOW` ×7, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×2, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×4, `UNMAPPED_TABLE_CONTENT` ×1, `VISUAL_MASK_TOO_LARGE` ×2 |
| DOC-008 | 22 | 3 | 0 | 0 | 169 | 0 | 0 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 |

### 5.4 OCR

| Document | Pages scannées | Confiance moteur ≥ 0,80 (part des car. attendus) run25e → run26 | Lignes tentées F25 | Récupérées | Confirmées | Blocs mis en revue | Exactitude caractère |
|---|---|---|---|---|---|---|---|
| DOC-001 | 2/2 | 0,965 → 0,966 | 6 | 1 | 0 | 5 | inconnue |
| DOC-002 | 1/1 | 0,790 → 0,790 | 4 | 0 | 0 | 3 | inconnue |
| DOC-003 | 1/1 | 1,000 → 1,000 | 0 | 0 | 0 | 0 | inconnue |
| DOC-004 | 2/2 | 0,754 → 0,802 | 32 | 15 | 1 | 15 | inconnue |
| DOC-005 | 2/2 | 0,825 → 0,825 | 7 | 0 | 0 | 6 | inconnue |
| DOC-006 | 16/16 | 0,985 → 0,985 | 37 | 0 | 1 | 25 | inconnue |
| DOC-007 | 5/5 | 0,759 → 0,760 | 35 | 0 | 1 | 24 | inconnue |
| DOC-008 | 2/2 | 0,943 → 0,951 | 2 | 0 | 1 | 1 | inconnue |

L'exactitude OCR caractère par caractère est **inconnue** : aucune transcription humaine n'existe. La confiance du
moteur n'est qu'un indicateur.

### 5.5 Vérification après rendu (F26)

| Document | Placements insérés | Vérifiés (rappel ≥ 0,90) | Non vérifiés | Non mesurables |
|---|---|---|---|---|
| DOC-001 | 9 | 9 | 0 | 0 |
| DOC-002 | 8 | 8 | 0 | 0 |
| DOC-003 | 2 | 2 | 0 | 0 |
| DOC-004 | 88 | 88 | 0 | 0 |
| DOC-005 | 3 | 3 | 0 | 0 |
| DOC-006 | 268 | 268 | 0 | 0 |
| DOC-007 | 87 | 87 | 0 | 0 |
| DOC-008 | 22 | 22 | 0 | 0 |

## 6. Comparaison visuelle

Les planches privées comparent, pour chaque page, l'original, `baseline`, `run17`, `run24`, `run25`, `run26a`, `run26`,
la différence run26/original et la différence run26/run26a. S'y ajoute un audit des régions graphiques : logos,
cachets, signatures, éléments vectoriels. Elles restent dans l'espace privé : 31 planches (une par page) et 8 audits
de régions, référencés dans chaque JSON (`private_visual_evidence`).

Observations faites sur les planches et les recadrages privés (sans reproduire de contenu) :

- **DOC-004, page 2** : run26 traduit quelques libellés de plus que run25e dans la colonne de gauche. Mais une
  grande partie du formulaire reste en langue source (libellés de la colonne centrale, cases à cocher), et de l'encre
  source reste visible sous un libellé de section, dans run25e comme dans run26. C'est cohérent avec sa couverture
  écrite de 0,580 et ses 17 débordements.
- **DOC-007, page 1** : en run25e, un libellé et sa valeur étaient traduits. En run26, F25 envoie le libellé en revue,
  car son OCR est non fiable. La valeur, bien lue par l'OCR et correctement traduite, **n'est plus rendue** : comme le
  libellé voisin n'est plus remplacé, le masque ne peut plus s'étendre sur lui, et de l'encre source reste sous la
  valeur (part d'encre 0,15). Le statut passe honnêtement de `TRANSLATED` à `FAILED:render_residual_source_ink`. Le
  résultat visible est **moins bon** pour ce champ : la source reste affichée. Aucune fausse traduction n'est montrée.
- **Contrôle F26** : quatre blocs que la mesure v2.1 classait partiels ou absents ont été relus visuellement. Leur
  cible est écrite en entier dans le cadre réel du moteur, plus large que la boîte OCR. Ce sont des artefacts
  conservateurs de la mesure, pas des troncatures. Un cinquième bloc de DOC-004 a bien sa cible complète, mais sa
  traduction est incohérente, car l'OCR a fusionné deux questions et du bruit. En plus, un filet de tableau traverse le
  texte rendu. **Aucun contrôle automatique ne détecte ce défaut** : voir les défauts ouverts.

## 7. Statut final par document

| Document | Statut | Justification |
|---|---|---|
| DOC-001 | `REVIEW_REQUIRED` | `CRITICAL_DEFECTS_PRESENT`, `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |
| DOC-002 | `REVIEW_REQUIRED` | `CRITICAL_DEFECTS_PRESENT`, `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |
| DOC-003 | `REVIEW_REQUIRED` | `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |
| DOC-004 | `REVIEW_REQUIRED` | `CRITICAL_DEFECTS_PRESENT`, `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |
| DOC-005 | `REVIEW_REQUIRED` | `CRITICAL_DEFECTS_PRESENT`, `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |
| DOC-006 | `REVIEW_REQUIRED` | `CRITICAL_DEFECTS_PRESENT`, `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |
| DOC-007 | `REVIEW_REQUIRED` | `CRITICAL_DEFECTS_PRESENT`, `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |
| DOC-008 | `REVIEW_REQUIRED` | `CRITICAL_DEFECTS_PRESENT`, `SCORE_LOWER_BOUND_BELOW_THRESHOLD`, `HUMAN_VALIDATION_NOT_PERFORMED`, `SEMANTIC_ACCURACY_UNKNOWN_NO_HUMAN_REFERENCE`, `HALLUCINATION_NOT_PROVEN_BY_REFERENCE`, `OCR_CHARACTER_ACCURACY_UNKNOWN_NO_HUMAN_TRANSCRIPTION` |

Aucun document ne peut être `VALIDATED` : la validation humaine n'a pas été faite, et la méthode l'exige.
