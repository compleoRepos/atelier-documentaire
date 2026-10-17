# RUN29 — Correction de bout en bout du moteur de traduction documentaire

Branche : `feature/run29-correction-bout-en-bout-20261016`, empilée sur le RUN28 (`feature/run28-moteur-simplification-20261014`, commit `0198654`).

**Verdict : NO-GO.** 8/8 documents `REVIEW_REQUIRED`, 0/1 072 ligne humaine revue, score officiel du corpus (borne basse v2, méthode gelée) 64,4737, seuil de 94 non atteint. Le RUN29 corrige des défauts réels et prouvés, mais ne rend pas le moteur apte à une mise en service bancaire.

## Rapports

| Rapport | Contenu |
|---|---|
| [RUN29-EXECUTIVE-SUMMARY.md](RUN29-EXECUTIVE-SUMMARY.md) | synthèse : verdict, tableau des 8 documents, corrections, défauts ouverts |
| [RUN29-DIAGNOSTIC.md](RUN29-DIAGNOSTIC.md) | diagnostic initial : défauts par document, étape responsable, gravité, preuve, causes racines |
| [RUN29-IMPLEMENTATION-CHANGES.md](RUN29-IMPLEMENTATION-CHANGES.md) | correctifs F43 à F53, fichiers modifiés, justification, empreintes des arbres testés |
| [RUN29-TESTS.md](RUN29-TESTS.md) | commandes, résultats, doubles de test identifiés, contre-épreuves, résultats invalidés |
| [RUN29-BEFORE-AFTER.md](RUN29-BEFORE-AFTER.md) | comparaison RUN28 / RUN29 à règle identique : score, quatre niveaux (sens, intégrité, couverture, format), défauts, statuts, transitions, contrôle visuel |
| [RUN29-ENGINE-COMPARISON.md](RUN29-ENGINE-COMPARISON.md) | gpt-oss-20b local contre Interim dans des conditions contrôlées |
| [RUN29-OPEN-ISSUES.md](RUN29-OPEN-ISSUES.md) | défauts ouverts, limites de mesure, prérequis manquants |
| [RUN29-DEPLOYMENT-VERDICT.md](RUN29-DEPLOYMENT-VERDICT.md) | verdict de mise en service motivé et conditions de levée |

## Exports anonymisés

[documents/](documents/) contient un fichier JSON par document (`DOC-001.json` à `DOC-008.json`) et un fichier corpus (`corpus.json`). Tous les chiffres des rapports se recalculent à partir de ces exports ; les tableaux des rapports sont générés depuis eux.

Ils ne contiennent **que** des identifiants anonymes `DOC-00x`, des compteurs, des scores, des codes d'anomalie et des descriptions génériques. Aucun texte source ou traduit, aucune coordonnée, aucun identifiant de bloc, aucun nom de fichier, chemin ou empreinte d'original, aucune autorisation et aucun artefact (PDF, image, planche, OCR, IR).

## Confidentialité

Les 8 originaux, leurs sorties (PDF traduits, aperçus, planches, agrandissements), l'OCR, l'IR, les traductions, la mémoire de traduction, l'autorisation Interim, les poids et journaux du modèle local restent dans un espace privé, hors de Git. Avant tout ajout au dépôt, le diff, les exports et les textes de la demande de fusion sont passés au scanner anti-fuite (empreintes, chemins, adresses, secrets, longues chaînes hexadécimales, n-grammes comparés à l'OCR et aux traductions du corpus).

## Reproduire

Les commandes exactes sont dans [RUN29-TESTS.md](RUN29-TESTS.md). Résumé :

```bash
# Suite backend (commande de la CI)
PYTHONPATH=backend pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security
# Golden : pipeline technique sur les 8 originaux confidentiels (copies locales non versionnées, moteur offline)
PYTHONPATH=backend pytest backend/tests/golden_dataset
# Analyse statique et audit
ruff check backend tools
pip-audit -r backend/requirements.txt --strict
```

Le rejeu du corpus réel exige les originaux et une autorisation privée valide : il n'est pas reproductible depuis le dépôt seul, par construction.
