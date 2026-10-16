# RUN28 — Simplification et remise à niveau du moteur de traduction documentaire privé

> **Verdict : seuil de 94 NON atteint, production bancaire bloquée.** 8/8 `REVIEW_REQUIRED`. Score officiel v2 du corpus 65,9 → 65,7 (borne haute 90,3). 42 défauts critiques mesurés (55 en RUN27). 0/1 072 ligne humaine revue. Voir [RUN28-EXECUTIVE-SUMMARY.md](RUN28-EXECUTIVE-SUMMARY.md).

## Rapports

| Fichier | Contenu |
| --- | --- |
| [RUN28-EXECUTIVE-SUMMARY.md](RUN28-EXECUTIVE-SUMMARY.md) | verdict, tableau des 8 documents, améliorations visibles / techniques, défauts corrigés / ouverts, validation humaine |
| [RUN28-ROOT-CAUSES.md](RUN28-ROOT-CAUSES.md) | cartographie du parcours en 9 étapes, complexités examinées, causes racines F35–F42, causes diagnostiquées non corrigées |
| [RUN28-IMPLEMENTATION-CHANGES.md](RUN28-IMPLEMENTATION-CHANGES.md) | fichiers modifiés, parcours A (XLSX/PPTX natifs), parcours B, traduction, interface, Qwen/vLLM |
| [RUN28-BEFORE-AFTER.md](RUN28-BEFORE-AFTER.md) | comparaisons à règle identique, explication du score, deux comptages critiques, transitions de statuts, PDF, provenance |
| [RUN28-REGRESSION-RESULTS.md](RUN28-REGRESSION-RESULTS.md) | empreintes, exécutions du corpus, suites, mutations, résultats invalidés, confidentialité, commits, CI |
| [RUN28-OPEN-ISSUES.md](RUN28-OPEN-ISSUES.md) | défauts et limites ouverts, éléments à valider humainement |
| [documents/](documents/) | `DOC-001.json` … `DOC-008.json` et `corpus.json` : exports anonymisés (identifiants, compteurs, ratios, codes) |

## Confidentialité

Ce dossier ne contient **aucun** original, OCR, IR, PDF, image, planche, texte de document, nom de fichier réel, empreinte d’original, autorisation, journal privé ou secret. Les PDF candidats des exécutions run28 à run28e, les planches comparatives (original | RUN27 | RUN28, agrandissements), le pack de validation humaine, les journaux, les scorecards complets et l’exporteur sont conservés dans l’**espace privé autorisé**, hors Git, avec un manifeste SHA-256.

L’audit anti-fuite RUN28 a couvert **tout le dépôt suivi**. Il a corrigé un défaut du scanner hérité (lignes ajoutées aux fichiers suivis non scannées) et expurgé la tête de branche des fragments documentaires hérités. **L’historique déjà poussé n’est pas réécrit** : décision requise, voir RUN28-OPEN-ISSUES, OI-16, et RUN28-REGRESSION-RESULTS § 7.

## Reproduire

Depuis la racine du dépôt, avec les artefacts privés des exécutions (chemins privés non publiés) :

1. Vérifier les gels v1 et v2 (`sha256sum -c` sur les manifestes privés).
2. Calculer l’empreinte de règle : `tools/recette/ruler_fingerprint.py`. Ne comparer que des mesures de même empreinte, ou mesurer les deux exécutions avec chacune des règles.
3. Mesurer : `tools/recette/measure_v2.py`, puis `tools/recette/scorecard.py` (v1) et `tools/recette/scorecard_v2.py` (v2), sorties **hors dépôt**.
4. Vérifier : `tools/recette/score_verify.py`.
5. Validation humaine : `tools/recette/human_validation.py export | ingest | status`, puis `scorecard_v2.py --review`.
