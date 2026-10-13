# RUN26 — Résultats de non-régression

Tous les résultats ci-dessous ont été **réellement exécutés** ; les journaux complets (JUnit, sorties pytest, empreintes)
sont conservés dans l'archive privée et ne sont pas versionnés. Une ligne « non exécuté » est écrite comme telle.

## 1. Empreintes du code testé

L'empreinte est un SHA-256 (tronqué à 16 caractères) de tous les fichiers Python de `backend/app` et `tools`
(code), ou de `backend/tests` (tests). Elle est calculée au début **et** à la fin de chaque exécution ; elle est
identique dans tous les cas ci-dessous.

| Empreinte | Contenu | Usage |
|---|---|---|
| code `449b3ab80ed0b263` | Code RUN26 complet (P0, score, F25 à F28) | Run de verdict du corpus, mesures, scorecard, suite backend et golden de verdict |
| code `a6f205945d90df80` | Même code, après retrait des valeurs issues des documents dans **des commentaires et une docstring** | Suite backend et golden finaux |
| tests `64e66d134f148b6d` | Arbre de tests final (valeurs synthétiques + tests de traçabilité P0) | Suite backend finale |

Passage de `449b3ab80ed0b263` à `a6f205945d90df80` : seuls des commentaires (`quality/engine.py`,
`documents/line_verification.py`) et une docstring et un commentaire (`documents/ocr_recovery.py`) ont changé. L'arbre
syntaxique Python de ces trois fichiers est **identique** avant et après (comparaison `ast.dump`, docstrings exclues
pour le troisième). Le comportement est donc celui qui a produit le run de verdict. Les suites ont malgré tout été
relancées sur le code final.

## 2. Corpus des 8 documents

| Contrôle | Run intermédiaire (run26) | Run de verdict (run26b) |
|---|---|---|
| Groupes d'exécution | 3, code retour 0 | 3, code retour 0 (96 s) |
| Requêtes Interim | 5 (DOC-001, DOC-004 ×2, DOC-007, DOC-008) | 0 (mémoire de traduction du run intermédiaire) |
| Traces de requête = requêtes envoyées | oui (5 = 5) | oui (0 = 0) |
| Réservation maximale de contexte | 17 379 tokens (≤ 32 768) | aucune requête |
| Violations du budget | 0 | 0 |
| Mode de génération | `MIXED_MEMORY_AND_NEW_GENERATION` ×4, `TRANSLATION_MEMORY_REUSE_ONLY` ×4 | `TRANSLATION_MEMORY_REUSE_ONLY` ×8, `model_invoked = false` |
| Intégrité des originaux (SHA-256 avant/après) | inchangés ×8 | inchangés ×8 |
| Statut | `REVIEW_REQUIRED` ×8 | `REVIEW_REQUIRED` ×8 |
| Vérification après rendu (F26) | — | 487 placements vérifiés sur 487 |

Les deux runs ont les mêmes entrées (analyse) et les mêmes cibles. Le run de verdict ne sert qu'à revalider F27/F28
sans nouvel appel au modèle. Les ensembles de codes critiques sont identiques entre les deux runs ; seuls les
compteurs corrigés par F27 changent.

## 3. Suites de tests

| Suite | Code / tests | Résultat | Durée |
|---|---|---|---|
| Backend, **périmètre exact de la CI** (unit, intégration, e2e, régression, sécurité) — final | `a6f205945d90df80` / `64e66d134f148b6d` | **659 passed**, 0 failed, 0 error, 0 skipped, 69 warnings | 210,4 s |
| Backend, même périmètre, après assainissement (avant ajout des tests P0) | `a6f205945d90df80` / `ae07383c946dab77` | 646 passed, 0 failed, 69 warnings | 203,1 s |
| Backend, même périmètre, code de verdict | `449b3ab80ed0b263` / `d1d700c49d69b472` | 646 passed, 0 failed, 69 warnings | 216,8 s |
| Golden dataset (8 documents), code de verdict | `449b3ab80ed0b263` | **8 passed**, 0 failed | 1 176,5 s |
| Golden dataset (8 documents), code final | `a6f205945d90df80` | **8 passed**, 0 failed, 0 error, 0 skipped, 63 warnings | 1 153,8 s |
| Frontend : `npm ci`, typecheck, tests, build (frontend inchangé depuis RUN25) | — | tous code retour 0 ; 6 fichiers, **16 tests passed** | — |

Les 69 avertissements sont des dépréciations de bibliothèques (aucun n'est un échec masqué).

### Tests ciblés RUN26

| Fichier | Couvre | Cas |
|---|---|---|
| `test_run26_regressions.py` | F25 (16), F26 (6), F27/F28 (5) | 27 |
| `test_run26_traceability.py` | P0 : traces, provenance, rapprochement, mode de génération, mémoire | 13 |
| `test_confidence_score.py` | Score `doc-confidence-1` : bornes, inconnues, plafond, défauts critiques, statut | 9 |

### Contre-épreuves (le test doit échouer si le correctif est retiré)

| Correctif neutralisé | Échecs observés | Attendu |
|---|---|---|
| F25 (relecture OCR désactivée) | 5 | ≥ 1 |
| F27 + F28 | 4 (le 5e test est un cas négatif) | 4 |
| P0 service et moteur (provenance et identifiant de réponse) | 8 sur 8 tests concernés | 8 |
| P0 lanceur (mémoire déclarée comme génération nouvelle) | 3 sur 3 cas avec mémoire | 3 |

## 4. Qualité de code et dépendances

| Contrôle | Résultat |
|---|---|
| `ruff check backend tools` (commande de la CI) | OK |
| `ruff format --check` sur tous les fichiers Python modifiés ou créés par RUN26 | OK |
| `ruff format --check backend tools` (global, **non lancé par la CI**) | 21 fichiers signalés, tous antérieurs à RUN26 et inchangés (voir défauts ouverts, OI-26) |
| `npm audit --audit-level=high` | 0 vulnérabilité |
| `pip-audit -r backend/requirements.txt --strict` | aucune vulnérabilité connue |
| `git diff --check` (fichiers suivis) et `git diff --cached --check` (périmètre du commit) | OK |

## 5. Reproductibilité du score

| Contrôle | Résultat |
|---|---|
| Gel de la méthode (SHA-256 de `confidence_score.py`, `scorecard.py`, `measure_v2.py`, `render_outcome.py`) | 4/4 identiques au gel, vérifié après chaque correctif et en fin de run |
| baseline, run24 et run25 recalculés par quatre invocations successives du scorecard | Identiques au dixième de point, document par document (63,1 / 67,9 / 68,0) |
| Run intermédiaire et run de verdict | Dimensions, défauts et statuts identiques (73,8) ; seule différence : le nombre de requêtes (5 → 0) |
| Invocation invalidée | Une invocation a donné 69,4 au run intermédiaire. Elle est **invalide** : ses planches visuelles omettaient ce run, si bien que l'audit des régions manquait et comptait 0. Elle a été remplacée par une invocation complète (6 runs) ; seule celle-ci est utilisée |

## 6. Confidentialité

| Contrôle | Résultat |
|---|---|
| Scanner anti-fuite privé (mots rares, séquences de 4 mots et nombres du corpus ; empreintes longues, noms de fichiers PDF, chemins privés, adresses, identifiants d'autorisation) sur **tout** l'arbre suivi + les nouveaux fichiers | Fuites trouvées et retirées (voir [causes racines](RUN26-ROOT-CAUSES.md), §8) ; scan final : uniquement des faux positifs qualifiés (compteurs, versions, années, tournures génériques, empreintes des fichiers de méthode, nom générique `candidate.pdf`) |
| Fichiers versionnés par RUN26 | code, tests synthétiques, outil de score, rapports et JSON anonymisés (`DOC-001` à `DOC-008`, compteurs, ratios, codes) |
| Non versionnés (privés) | originaux, OCR, IR, PDF candidats, planches et recadrages, SHA réels, autorisation, journaux, mémoire de traduction, scanner anti-fuite |
| Historique Git antérieur | contient encore des valeurs issues des documents (OI-24) : réécriture non faite, à décider |

## 7. CI GitHub

Workflow « Private document translator », déclenché par la PR brouillon #4 (événement `pull_request`), sur le commit
`b61f25ad395b23b35fc2639e928684d04315b50e` (code + rapports) :
[run 38325019292](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/38325019292) — **success**.

| Job | Conclusion |
|---|---|
| `frontend` | success |
| `backend` | success |
| `backend-integration-and-migrations` | success |
| `container-and-manifest-validation` | success |
| `private-acceptance` | skipped (porte privée, non exécutable en CI publique) |
| `manual-release-gate` | skipped (porte de publication manuelle, volontairement non déclenchée) |

Le commit qui ajoute cette section ne modifie que les rapports ; sa propre CI est suivie de la même façon. Un succès de
la CI ne vaut **pas** recette : le corpus reste `REVIEW_REQUIRED` et la publication reste bloquée.
