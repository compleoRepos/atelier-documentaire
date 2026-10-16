# RUN26 — Score de confiance documentaire

> **Seuil de 94/100 non atteint.** Score officiel du corpus : **73,8/100** (borne basse ; borne haute 90,6), contre
> 68,0 au RUN25. 0 document sur 8 au seuil ; 8 documents sur 8 `REVIEW_REQUIRED` ; aucune validation humaine.
> **Mise en production et validation humaine bloquées.**

## Contenu

| Fichier | Contenu |
|---|---|
| [RUN26-EXECUTIVE-SUMMARY.md](RUN26-EXECUTIVE-SUMMARY.md) | Verdict, chiffres clés, tableau récapitulatif des 8 documents |
| [RUN26-SCORE-METHODOLOGY.md](RUN26-SCORE-METHODOLOGY.md) | Formule du score, dimensions, inconnues, plafond structurel, défauts critiques, gel de la méthode, dictionnaire des métriques |
| [RUN26-BEFORE-AFTER.md](RUN26-BEFORE-AFTER.md) | Audit de la divergence RUN25, comparaison baseline / run24 / run25 / run26, par document et par dimension |
| [RUN26-ROOT-CAUSES.md](RUN26-ROOT-CAUSES.md) | Causes, correctifs, tests et contre-épreuves (P0, F25 à F28, confidentialité) |
| [RUN26-REGRESSION-RESULTS.md](RUN26-REGRESSION-RESULTS.md) | Corpus, suites de tests, contre-épreuves, audits, reproductibilité, CI |
| [RUN26-OPEN-ISSUES.md](RUN26-OPEN-ISSUES.md) | Défauts et questions ouverts, pistes de correction sans promesse |
| [documents/](documents/) | Un JSON anonymisé par document (`DOC-001.json` à `DOC-008.json`) et `corpus.json` |

## Source de vérité

- Mesure : `tools/recette/measure_v2.py` (`measure-v2.1-run18`), identique pour tous les runs comparés.
- Score : `tools/recette/scorecard.py` (`scorecard-1`) et `backend/app/documents/confidence_score.py`
  (`doc-confidence-1`). Méthode gelée avant les correctifs ; empreintes dans la méthodologie, §8.
- Run de verdict : run26b (code `449b3ab80ed0b263`). Les JSON de `documents/` sont générés à partir de la seule
  invocation complète du scorecard (6 runs, avec l'audit visuel des régions pour chacun).

## Confidentialité

Ce dossier ne contient **aucun** contenu de document : ni texte, ni image, ni nom de fichier, ni empreinte réelle, ni
métadonnée, ni coordonnée. Les documents sont désignés par `DOC-001` à `DOC-008`. Les originaux, l'OCR, les
représentations intermédiaires, les PDF produits, les planches visuelles, la mémoire de traduction, l'autorisation du
propriétaire des données et les journaux d'exécution restent **privés, hors Git**.

## Reproduire le score

Sur le poste privé qui détient le corpus et les sorties d'exécution (chemins privés non publiés) :

1. vérifier le gel : `sha256sum -c` sur le fichier d'empreintes de la méthode ;
2. mesurer chaque run avec `tools/recette/measure_v2.py` ;
3. produire les planches visuelles de **tous** les runs comparés (`tools/recette/compare_runs_sheets.py`) ;
4. calculer le score : `tools/recette/scorecard.py`, dont la sortie doit être écrite hors du dépôt.

Une invocation dont les planches omettent un run est invalide pour ce run (voir
[résultats de non-régression](RUN26-REGRESSION-RESULTS.md), §5).
