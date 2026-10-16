# RUN26 — Méthodologie du score de confiance documentaire

> Méthode **gelée le 2026-10-12 à 22:16:48Z**, avant tout correctif RUN26 et avant le run du corpus RUN26.
> Elle n'a pas été modifiée ensuite : les empreintes SHA-256 des quatre fichiers de méthode (tableau §8) ont été
> recontrôlées après les correctifs, et elles sont identiques.

## 1. Pourquoi un nouveau score

Les scores historiques sont conservés tels quels (compatibilité), mais ils ne permettent **pas** d'affirmer une
confiance :

| Score existant | Où | Valeur observée sur run25 | Limite |
|---|---|---|---|
| `GLOBAL`, `STRUCTURE`, `TABLE`, `ENTITY` | `fidelity_report.fidelity_scores` | toujours `None` | jamais calculés sur PDF scanné |
| `LAYOUT` | idem | 0,47 à 0,76 | géométrie seule, sans contrôle de ce qui est écrit |
| `TEXT` | idem | 0,54 à 1,0 | proportion de blocs géométriques, pas la couverture traduite |
| `VISUAL` | idem | 0,0 (DOC-004/006/007), sinon 0,87 à 0,94 | forcé à 0 dès qu'une alerte critique existe |
| `ocr`, `translation`, `semantic` | moteur qualité `evaluate_quality` | `None` | aucune référence humaine disponible |

Ces scores ne mesurent ni la couverture réellement écrite dans le PDF, ni les entités, ni l'intégrité des preuves.
Aucun ne fait la différence entre « inconnu » et « bon ».

RUN26 garde ces scores et ajoute un **score de confiance documentaire**, explicite et reproductible :

- module produit `backend/app/documents/confidence_score.py`, version `doc-confidence-1` : fonction pure qui ne fait
  aucune entrée-sortie ;
- outil de recette `tools/recette/scorecard.py`, version `scorecard-1` : il collecte les composantes **depuis les
  artefacts produits** et appelle le module produit. C'est la source de vérité unique : aucun chiffre de score n'est
  saisi à la main.

## 2. Formule

- **Huit dimensions** à poids fixes, dont la somme fait 100.
- Chaque dimension est la **moyenne de ses sous-composantes**. Une sous-composante est :
  - soit un ratio dans [0, 1] calculé depuis les artefacts ;
  - soit `None`, c'est-à-dire **non mesurée** (pas de référence humaine, pas de vérité terrain) ;
  - soit `NOT_APPLICABLE` (rien à contrôler, par exemple aucun nombre dans les blocs traduits).
- Une valeur **inconnue n'est jamais notée** : elle compte **0 dans la borne basse** et **1 dans la borne haute**.
- `NOT_APPLICABLE` sort la sous-composante de la moyenne de sa dimension. Quand toutes les sous-composantes d'une
  dimension sont non applicables, la dimension sort du calcul et son poids est redistribué. C'est la **seule**
  renormalisation, et elle ne s'applique jamais à une valeur inconnue.
- **Score officiel = borne basse** :
  `score = 100 × Σ(poids × min_dim) / Σ(poids des dimensions applicables)`.
  La borne haute montre ce qui n'est pas prouvé.
- **Le seuil de 94 est atteint** seulement si **les deux** conditions sont réunies : borne basse ≥ 94 **et** aucun
  défaut critique connu, ni blocage.
- **Statut** :
  - `BLOCKED` si une preuve bloquante manque ;
  - sinon `REVIEW_REQUIRED` s'il existe un défaut critique **ou** s'il n'y a pas de validation humaine autorisée ;
  - `VALIDATED` est impossible sans validation humaine. Aucun document ne peut donc l'obtenir dans cette recette.
- **Corpus** : moyenne simple des bornes basses des 8 documents, chaque document ayant le même poids, pour qu'un petit
  document difficile ne soit pas dilué. Le seuil du corpus suppose aussi qu'aucun document n'a de défaut critique.

## 3. Dimensions, sous-composantes, numérateurs et dénominateurs

Sources :

- « PDF » = mesure indépendante `measure_v2` v2.1 / `render_outcome`, qui relit les mots réellement présents dans le
  PDF produit ;
- « IR » = `analysis.json` ;
- « TR » = `translation.json` ;
- « RS » = `interim-run-summary.json` ;
- « J » = `execution-journal.jsonl` ;
- « RV » = audit des régions visuelles `compare_runs_sheets`.

| Dimension (poids) | Sous-composante | Numérateur / dénominateur | Source | Inconnu ou non applicable |
|---|---|---|---|---|
| Couverture textuelle écrite (20) | `written_share` | caractères attendus effectivement écrits / caractères attendus | PDF | attendu = 0 → non applicable |
| Confiance de traduction (15) | `target_language` | caractères traduits dont la cible est reconnue française / caractères traduits **évaluables** | TR + lexique | lexique absent → inconnu |
| | `semantic_accuracy` | exactitude contre une référence humaine validée | — | **toujours inconnu** (pas de référence) |
| Fidélité au document source (10) | `pages_preserved` | 1 si le PDF a le même nombre de pages que la source, sinon 0 | PDF + IR | PDF illisible → inconnu |
| | `regions_unaltered` | 1 − régions graphiques ou protégées altérées (> 2 % de pixels) / régions détectées | RV | 0 région → non applicable |
| Préservation des entités (15) | `digit_sequences` | blocs traduits dont la suite de nombres est identique à la source / blocs traduits contenant des nombres | IR + TR | aucun nombre → non applicable |
| Mise en page (10) | `no_text_over_ink` | 1 − blocs écrits sur encre source résiduelle / blocs mesurés | PDF | |
| | `no_collision` | 1 − mots insérés en collision / mots insérés | PDF | |
| | `in_page` | 1 − mots insérés hors page / mots insérés | PDF | |
| | `not_truncated` | 1 − blocs PARTIAL / blocs mesurés | PDF | |
| Qualité OCR (10) | `engine_confidence` | caractères attendus de confiance OCR du moteur ≥ 0,80 / caractères attendus. C'est un **indicateur**, pas une exactitude | IR | aucune page scannée → non applicable |
| | `character_accuracy` | exactitude caractère contre une transcription humaine | — | **toujours inconnu** sur scan |
| Absence d'hallucination (10) | `no_unreliable_source_translated` | 1 − caractères traduits depuis un OCR de confiance < 0,60 / caractères traduits | IR + TR | |
| | `no_length_anomaly` | 1 − caractères traduits avec un rapport cible/source > 3 ou < 1/3 (source ≥ 20 caractères) / caractères traduits | IR + TR | |
| | `proven_by_reference` | absence d'ajout ou d'omission prouvée contre une référence humaine | — | **toujours inconnu** |
| Complétude des preuves (10) | `original_unchanged` | SHA-256 de l'original identique avant et après | RS | |
| | `block_provenance` | chaque bloc a une origine déclarée (appel modèle, mémoire, non envoyé) | TR | |
| | `request_reconciliation` | traces de requêtes = `requests_sent`, chaque trace ayant un identifiant de corrélation et un identifiant de réponse | TR | |
| | `generation_mode` | mode de génération déclaré parmi 5 valeurs | RS | |
| | `execution_journal` | journal horodaté avec empreinte de code et HEAD Git | J | |
| | `candidate_produced` | PDF reconstruit présent et lisible | PDF | |
| | `budget_respected` | 0 violation **et** réservation maximale ≤ 32 768 quand des requêtes ont été envoyées | RS | |

Règles de détail :

- **Bloc traduit** : bloc dont la cible diffère de la source au sens de `measure_v2.changed`, qui ignore la casse,
  les espaces et la ponctuation typographique.
- **Attendu** : périmètre `measure_v2.expected_scope`. La langue est recalculée avec la même règle pour tous les runs
  (§2 du rapport run18), et le dénominateur ne dépend pas du run.
- **Cible française** :
  - moins de 50 % de lettres latines → non français ;
  - mots évalués : au moins 3 lettres, en minuscules ou en CAPITALES. Les mots à majuscule initiale (noms propres,
    sociétés, lieux, conservés volontairement) sont exclus ;
  - les adresses e-mail et URL sont retirées ;
  - un mot est **étranger** s'il est courant dans une langue du document (zipf ≥ 3) et plus courant qu'en français
    d'au moins 1,0, comme dans la règle `language_evidence` ;
  - la cible est française si les mots étrangers représentent au plus 20 % des mots informatifs. Elle est non
    évaluable (exclue du dénominateur) s'il ne reste aucun mot informatif.
- **Suite de nombres** : chiffres ASCII et chiffres non ASCII convertis, dans l'ordre d'apparition.

## 4. Défauts critiques (bloquants pour le seuil)

Un défaut critique empêche d'atteindre le seuil, **quelle que soit la moyenne**.

| Source | Codes |
|---|---|
| Produit | tout code d'alerte de sévérité `critical` émis par le pipeline pour le document : débordement, encre résiduelle, entité modifiée, région protégée, tableau non relié, cible non vérifiée F26, etc. Comptage par code, depuis `measure_v2.critical_codes` |
| Scorecard | `ENTITY_DIGITS_MISMATCH` : nombres différents entre source et cible ; `ENTITY_DIGITS_REORDERED` : mêmes nombres dans un autre ordre |
| Blocages (`BLOCKED`) | `ORIGINAL_INTEGRITY_NOT_PROVEN`, `CANDIDATE_MISSING`, `EVIDENCE_REQUEST_COUNT_MISMATCH` |

Le prompt cite les catégories montant, nom, date, clause et banque. Le contrôle automatique ne couvre que les
**nombres** (montants, dates, identifiants, IBAN). Les noms et les clauses ne sont **pas** vérifiables sans référence
humaine : ils restent dans la part inconnue (`semantic_accuracy`, `proven_by_reference`) et ne sont jamais comptés
comme bons.

## 5. Plafond structurel

Sans références humaines, trois sous-composantes restent inconnues :

- `translation.semantic_accuracy` : 15 × 1/2 = 7,5 points perdus ;
- `ocr.character_accuracy` : 10 × 1/2 = 5,0 points, sur les documents scannés ;
- `hallucination.proven_by_reference` : 10 × 1/3 = 3,3 points.

Le meilleur score officiel possible est donc **84,2/100** (`confidence_score.structural_ceiling`), **même avec un
document parfait par ailleurs**. Le seuil de 94 est **inatteignable par construction** tant qu'aucune référence humaine
n'existe. Ce n'est pas un défaut de la recette : c'est la conséquence voulue de la règle « inconnu ≠ 100 ». Le relever
sans référence reviendrait à transformer des inconnues en résultats positifs, ce que le prompt interdit.

Ce qui peut faire atteindre 94 :

1. des traductions de référence validées par un humain autorisé, pour mesurer `semantic_accuracy` ;
2. une transcription humaine des scans, pour `character_accuracy` ;
3. une revue humaine des ajouts et omissions, pour `proven_by_reference` ;
4. zéro défaut critique.

## 6. Ce que le score n'est pas

- Ce n'est pas une mesure de qualité linguistique : aucune référence n'existe.
- Ce n'est pas une validation : le statut maximal reste `REVIEW_REQUIRED`.
- Le score ne compare pas des runs mesurés avec des méthodes différentes : avant et après sont calculés **avec la même
  version** (`doc-confidence-1`, `scorecard-1`, mesure v2.1) sur les artefacts de chaque run.

## 7. Reproduire

```bash
# 1. mesure indépendante v2.1 des runs (hors dépôt)
PYTHONPATH=backend:tools/recette python tools/recette/measure_v2.py --help
# 2. audit des régions visuelles (planches, hors dépôt)
PYTHONPATH=backend:tools/recette python tools/recette/compare_runs_sheets.py --help
# 3. score
PYTHONPATH=backend:tools/recette python tools/recette/scorecard.py \
    --metrics MESURE.json --sheets PLANCHES/ --run run25=SORTIES_RUN25 --run run26=SORTIES_RUN26 --out HORS_DEPOT.json
```

Les sorties sont refusées si elles sont écrites dans le dépôt. Elles ne contiennent que des compteurs, des ratios et des
codes, jamais de texte.

## 8. Empreintes de gel (22:16:48Z)

| Fichier | SHA-256 |
|---|---|
| `backend/app/documents/confidence_score.py` | `853f1af00affad38124fc8bb6b660bc62bf983d7a012b6366a11667ae54b1a03` |
| `tools/recette/scorecard.py` | `14c2118ffe9dd2bb24d54d98e7a444d38dcc53778fdc0fc90f1ef03fff275049` |
| `tools/recette/measure_v2.py` | `f7927a631d7c9ee849baa3ec2ab9e11562fc8fd5f75ceb4e7c1688b2d42ffbf4` |
| `tools/recette/render_outcome.py` | `f577717e307cb3d33eae09cd5d518dc403f9220c98b502c5ab9629fb4d1f8860` |

Contrôle après les correctifs F25 et F26 : `sha256sum -c` → 4/4 OK.

Un seul ajustement a eu lieu **avant** le gel, sur la règle de langue cible. La première règle (« mots français
courants ») pénalisait les noms propres et les adresses conservés à raison. La règle finale est celle du §3. Aucun
ajustement n'a été fait après le gel.

## 9. Application finale (verdict RUN26)

Cette section décrit comment la méthode a été appliquée. Elle ne modifie **ni la formule, ni les poids, ni les règles**
des §2 à §5.

### 9.1 Source de vérité unique

Tous les chiffres des rapports RUN26 et des JSON `documents/DOC-00x.json` viennent de **trois fichiers privés**,
produits par une seule chaîne d'outils versionnés et recalculés depuis les artefacts :

| Fichier privé (hors dépôt) | Outil | Version | Contenu |
|---|---|---|---|
| mesure v2.1 des 6 runs | `tools/recette/measure_v2.py` | `measure-v2.1-run18` | couverture, statuts, rendu, codes critiques |
| planches et audit des régions (6 runs) | `tools/recette/compare_runs_sheets.py` | — | régions graphiques altérées, planches visuelles |
| scorecard final | `tools/recette/scorecard.py` + `confidence_score.py` | `scorecard-1` / `doc-confidence-1` | scores, dimensions, défauts critiques |

Runs mesurés : `baseline` (référence du 08/10), `run17`, `run24`, `run25` (= run25e, verdict RUN25), `run26a` (run26
intermédiaire, F25 + F26 + preuves P0) et `run26` (= run26b, **verdict RUN26**, + F27 + F28).

Contrôle du gel (`sha256sum -c`, 4/4 OK) refait **après F25/F26**, **après F27/F28**, puis **avant la mesure finale**
et **avant le calcul du scorecard final**.

### 9.2 Scorecard intermédiaire invalidé

Un premier scorecard du verdict a été calculé avec des planches générées **sans** le run `run26a`. Faute d'audit de
régions, `regions_unaltered` y valait « inconnu » pour `run26a`, donc 0 en borne basse : `run26a` y obtenait 69,4.
Ce chiffre est **un artefact de mesure** et n'est cité nulle part. Les planches ont été régénérées avec les 6 runs ;
le scorecard final donne `run26a` = 73,8 [90,6], identique au scorecard calculé juste après le run intermédiaire.
`baseline`, `run24` et `run25` sont identiques, document par document, dans les quatre scorecards successifs
(avant correctifs, après run26a, verdict, final) : le calcul est reproductible.

### 9.3 Précision sur le dénominateur « attendu »

Le §3 indique que « le dénominateur ne dépend pas du run ». C'est vrai de la **règle** (même périmètre, même règle de
langue pour tous les runs). Mais sur un document scanné, le texte source est celui de l'OCR **du run**. RUN26 relit
16 lignes OCR (F25) : le nombre de caractères attendus passe de 42 967 (run25e) à 43 097 (run26) sur le corpus
(DOC-004 et DOC-001). La baseline (43 085) et run17 (42 652) diffèrent pour la même raison. Les ratios restent
comparables, car chacun est calculé avec la même règle sur le texte réellement traité.

### 9.4 Dictionnaire des métriques des rapports

Toutes les métriques portent sur les **8 documents**, sans exclusion de document. Unité : caractères non blancs du
texte source, sauf mention contraire.

| Métrique | Définition | Numérateur / dénominateur | Exclusions | Valeur nulle ou absente |
|---|---|---|---|---|
| Attendus | caractères source qui doivent être traduits | périmètre `measure_v2.expected_scope` | hors périmètre déclaré : déjà en français, identique en français, identifiant ou nombre, nom propre ou référence, sans contenu linguistique (ventilé dans les JSON) | 0 attendu → couverture non applicable |
| Tentés | attendus pour lesquels une cible différente de la source existe | tentés / attendus | — | — |
| Écrits | attendus dont la cible est relue dans le PDF produit, dans la zone du bloc | écrits / attendus = **couverture écrite** | — | PDF illisible → inconnu (aucun cas) |
| Partiels | cible présente en partie seulement dans le PDF | caractères source des blocs PARTIAL | — | — |
| Absents | cible tentée mais absente du PDF | caractères source des blocs ABSENT | — | — |
| Non tentés | attendus sans cible (échec, incertain, refus) | ventilés par raison de statut | — | — |
| Statuts de blocs | `TRANSLATED`, `FAILED`, `UNCERTAIN`, `PRESERVED_INTENTIONALLY`, `NOT_TRANSLATABLE`, `NOT_PROCESSED` | nombre de blocs par statut, avec raison | — | bloc sans statut → `NOT_PROCESSED` (0 cas) |
| Défauts critiques | occurrences d'alertes de sévérité `critical` par code, plus les défauts calculés par le scorecard | comptage par code | aucune | — |
| F25 | lignes OCR relues sur copie prétraitée | tentées, récupérées, confirmées, refusées par motif ; blocs mis en revue | blocs déjà non fiables ou protégés | — |
| F26 | placements réellement insérés dans le PDF et relus | vérifiés / placements (rappel des jetons cible ≥ 0,90 dans le cadre du moteur) | — | non mesurable → compté à part (0 cas) |
| Provenance | origine déclarée de chaque bloc | `MODEL_CALL`, `TRANSLATION_MEMORY`, `NOT_SENT`, etc. | — | bloc sans origine → preuve incomplète |

### 9.5 Reproduire le verdict

```bash
export OMP_THREAD_LIMIT=1 PYTHONPATH=backend:tools/recette
RUNS="--run baseline=B --run run17=R17 --run run24=R24 --run run25=R25 --run run26a=R26A --run run26=R26"
sha256sum -c METHOD-FREEZE.sha256                                     # gel : 4/4 OK requis
python tools/recette/measure_v2.py $RUNS --out HORS_DEPOT/v21.json
python tools/recette/compare_runs_sheets.py $RUNS --dest HORS_DEPOT/planches
python tools/recette/scorecard.py --metrics HORS_DEPOT/v21.json --sheets HORS_DEPOT/planches \
    --run baseline=B --run run24=R24 --run run25=R25 --run run26a=R26A --run run26=R26 --out HORS_DEPOT/scorecard.json
```

`B`, `R17`… désignent les dossiers de sortie privés de chaque run. Ils ne sont pas dans le dépôt.
