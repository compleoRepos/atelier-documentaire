# RUN27 — Audit du score, correction des causes racines et validation humaine

> **Verdict : seuil de 94/100 NON atteint.** Score officiel du corpus (borne basse v2) : **63,5 → 65,9**, borne haute 90,2, plafond 75,8. **0 document `VALIDATED`, 8 `REVIEW_REQUIRED`.** 94 est mathématiquement inaccessible sans références humaines (pack prêt, 0 ligne revue sur 1 072). Défauts critiques mesurés : 105 → 55, dont 30 en moins par simple correction de la mesure. Défauts critiques vérifiés à l’œil sur les PDF : 2 → 1, avec une **régression RUN27** (MV-01). La mise en production reste bloquée.

## Tableau final

| Document | Score v2 avant → après [borne haute] | Critiques mesurés avant → après | Critiques vérifiés à l’œil avant → après | Couverture écrite avant → après | PDF vs RUN26 | Référence humaine | Statut final |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 63,1 → **63,1** [86,4] | 3 → 3 | 0 → 0 | 58,8 % → 58,8 % | identique | NOT_STARTED (0/47) | **REVIEW_REQUIRED** |
| DOC-002 | 60,3 → **66,7** [89,9] | 5 → 4 | 0 → 0 | 39,3 % → 64,4 % | 1 p. modifiée(s) | NOT_STARTED (0/24) | **REVIEW_REQUIRED** |
| DOC-003 | 62,7 → **62,7** [94,2] | 0 → 0 | 0 → 0 | 74,1 % → 74,1 % | identique | NOT_STARTED (0/13) | **REVIEW_REQUIRED** |
| DOC-004 | 65,1 → **66,2** [89,4] | 31 → 25 | 0 → 0 | 58,0 % → 61,8 % | 2 p. modifiée(s) | NOT_STARTED (0/229) | **REVIEW_REQUIRED** |
| DOC-005 | 47,7 → **58,3** [81,5] | 5 → 0 | 0 → 1 | 21,3 % → 21,3 % | 1 p. modifiée(s) | NOT_STARTED (0/89) | **REVIEW_REQUIRED** |
| DOC-006 | 73,2 → **73,4** [96,7] | 36 → 7 | 0 → 0 | 93,7 % → 93,7 % | 1 p. modifiée(s) | NOT_STARTED (0/418) | **REVIEW_REQUIRED** |
| DOC-007 | 69,4 → **70,3** [93,6] | 20 → 11 | 2 → 0 | 76,6 % → 79,6 % | 2 p. modifiée(s) | NOT_STARTED (0/178) | **REVIEW_REQUIRED** |
| DOC-008 | 66,4 → **66,4** [89,7] | 5 → 5 | 0 → 0 | 59,1 % → 59,1 % | aucun changement visible | NOT_STARTED (0/74) | **REVIEW_REQUIRED** |
| **Corpus** | 63,5 → **65,9** [90,2] | 105 → 55 | 2 → 1 | 83,6 % → 85,0 % | 5/8 docs à changement visible | NOT_STARTED (0/1 072) | **REVIEW_REQUIRED** |

Notes de lecture :

- Scores : méthode `doc-confidence-2` gelée, **règle de mesure RUN27**, borne basse officielle arrondie vers le bas, borne haute vers le haut. Avant = run26 (verdict RUN26), après = run27 (verdict RUN27, run27b), mêmes huit originaux.
- DOC-005 : le gain (+10,5) n’est **pas revendiqué**. Il est dû pour 8,33 points à un angle mort de la mesure (entités comparées à l’OCR) qui récompense un identifiant devenu faux (MV-01).
- DOC-001 et DOC-003 : PDF identiques au pixel près ; DOC-008 : aucun changement visible. Aucune amélioration revendiquée pour ces trois documents.
- Couverture du corpus pondérée par les caractères ; le score pondère chaque document également.
- **Une borne haute ≥ 94 (DOC-003 : 94,2 ; DOC-006 : 96,7) n’est pas un seuil atteint** : elle suppose que toutes les inconnues seraient parfaites. Le score officiel est la borne basse, plafonnée à 76,8 (68,5 pour DOC-003) tant que les références humaines manquent.

## Rapports

| Fichier | Contenu |
| --- | --- |
| [RUN27-SCORE-AUDIT.md](RUN27-SCORE-AUDIT.md) | contradiction 73,8 / 90,6 / 84,2 expliquée, effet des preuves, v2, dérive de la règle de mesure, verdict de mesure |
| [RUN27-SCORE-MATHEMATICAL-VERIFICATION.md](RUN27-SCORE-MATHEMATICAL-VERIFICATION.md) | formule exacte, exemple recalculable, identités sur 8 documents, vérificateur indépendant, cas de test, mutations |
| [RUN27-ROOT-CAUSES.md](RUN27-ROOT-CAUSES.md) | reproduction, cause, correctif, test et effet mesuré de F29 à F34 ; défauts vus seulement sur les PDF |
| [RUN27-BEFORE-AFTER.md](RUN27-BEFORE-AFTER.md) | comparaisons à règle identique : corpus, documents, origine du gain, défauts, couverture, PDF, provenance |
| [RUN27-HUMAN-VALIDATION-PACK.md](RUN27-HUMAN-VALIDATION-PACK.md) | outil, format, règles d’autorisation, calcul par intervalles, état réel (NOT_STARTED) |
| [RUN27-REGRESSION-RESULTS.md](RUN27-REGRESSION-RESULTS.md) | empreintes, corpus, suites, mutations, PDF, confidentialité, CI |
| [RUN27-OPEN-ISSUES.md](RUN27-OPEN-ISSUES.md) | défauts et limites ouverts, corrections nécessaires, prérequis |
| [documents/](documents/) | `DOC-001.json` … `DOC-008.json` et `corpus.json` : exports anonymisés (identifiants, compteurs, ratios, codes) |

## Confidentialité

Ce dossier ne contient **aucun** original, OCR, IR, PDF, image, planche, texte de document, nom de fichier réel, empreinte d’original, autorisation, journal privé ou secret. Les PDF candidats, les planches comparatives (original | baseline | run17 | run24 | run25 | run26 | run27), les planches de différences, le pack de validation humaine, les journaux et les scorecards complets sont conservés dans l’**espace privé autorisé**, avec un manifeste SHA-256, hors Git.

## Reproduire

Depuis la racine du dépôt, avec les artefacts privés des runs (chemins privés non publiés) :

1. Vérifier les gels : `sha256sum -c` sur les manifestes privés v1 (4 fichiers) et v2 (8 fichiers).
2. Mesurer : `tools/recette/measure_v2.py` (v2.1) sur les répertoires de runs, puis `tools/recette/scorecard.py` (v1) et `tools/recette/scorecard_v2.py` (v2), sorties **hors dépôt**.
3. Vérifier : `tools/recette/score_verify.py` (fractions exactes, tables de poids indépendantes).
4. Comparer uniquement des mesures dont `tools/recette/ruler_fingerprint.py` donne la même empreinte de règle.
5. Validation humaine : `tools/recette/human_validation.py export | ingest | status`, puis `scorecard_v2.py --review`.
