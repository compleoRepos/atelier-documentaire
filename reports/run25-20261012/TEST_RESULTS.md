# RUN25 — Résultats des tests

Tous les résultats ci-dessous portent sur le code final, d'empreinte **`f4a84aaef38c7c7d`**. Cette empreinte est
calculée sur `backend/app` et `tools`, et elle est identique au début et à la fin de chaque exécution. C'est le même
code que celui du run final run25e. Les journaux et fichiers JUnit sont privés, dans l'archive de preuves.

## 1. Suite backend (périmètre exact de la CI)

| Élément | Valeur |
|---|---|
| Commande | `PYTHONPATH=backend pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security --junitxml=…` (identique à `.github/workflows/ci.yml`) |
| Résultat | **610 passed, 0 failed, 0 error, 0 skipped**, 69 avertissements |
| Durée | 220,52 s |
| Empreinte du code (début = fin) | `f4a84aaef38c7c7d` |
| Empreinte des tests (début = fin) | `b263dbccf67e5b3b` |
| JUnit | 610 tests, 0 failure, 0 error, 0 skipped |
| Environnement | Python 3.12.3, pytest 9.1.1 |

* Décompte : 591 tests au départ (`026b0f9`, résultat run18), plus 19 tests nouveaux dans
  `test_run25_regressions.py`, soit 610.
* Aucun test existant n'a été modifié, supprimé ni marqué `skip`.

Exécutions intermédiaires, chacune sur son code, sans valeur de verdict :

| Code | Correctifs | Résultat |
|---|---|---|
| `0c1d77bf17abe555` | F20, F20b, F21 | 599 passed |
| `12cd5235d720627c` | + F22 | 603 passed |
| `889fd05e1dd1fbfb` | + F22b | 604 passed |
| `e1e041cfccaae48e` | + F23 | 606 passed |
| `f4a84aaef38c7c7d` | + F24 (final) | **610 passed** |

Une relance limitée à unit et integration a été identifiée comme erreur de périmètre, renommée, puis remplacée par
le périmètre exact de la CI.

## 2. Tests de régression run25 (synthétiques)

`backend/tests/unit/test_run25_regressions.py` : **19 passed**.

| Correctif | Tests | Contre-épreuve (correctif neutralisé) |
|---|---|---|
| F20 | 4 | — |
| F20b | 2 | — |
| F21 | 2 | — |
| F22 | 4 | — |
| F22b | 1 | échoue sans F22b |
| F23 | 2 | le cas positif échoue sans F23 |
| F24 | 4 | 3 échecs, et 1 succès pour le cas négatif |

Les pages, l'encre, les boîtes et les jetons de ces tests sont entièrement synthétiques : aucun contenu de document
réel.

## 3. Golden local

| Élément | Valeur |
|---|---|
| Commande | `PYTHONPATH=backend pytest backend/tests/golden_dataset` (même cible que le job de CI privé), avec JUnit |
| Résultat | **8 passed, 0 failed**, 63 avertissements |
| Durée | 1 156,82 s |
| Empreinte du code (début = fin) | `f4a84aaef38c7c7d` |

* Portée : les 8 cas du golden local font une analyse neuve avec le moteur hors ligne, sans Interim. Ils vérifient les
  invariants techniques du test : statut de revue, empreintes inchangées, artefacts produits.
* Ils ne valident **ni** la qualité de la traduction **ni** la fidélité métier, faute de référence humaine.
* Golden intermédiaires :
  * `0c1d77bf17abe555` et `e1e041cfccaae48e` : 8 passed chacun ;
  * `12cd5235d720627c` et `889fd05e1dd1fbfb` : arrêtés quand le code a changé, non comptés.

  Seul le golden sur `f4a84aaef38c7c7d` vaut pour le code final.

## 4. Frontend Angular

| Étape | Commande (CI) | Résultat |
|---|---|---|
| Typecheck | `npm run typecheck` | rc 0 (5 s) |
| Tests | `npm test` | **16 passed** (6 fichiers), rc 0 (13 s) |
| Build de production | `npm run build` | rc 0 (8 s) |
| Audit | `npm audit --audit-level=high` | **0 vulnérabilité**, rc 0 |

Le frontend n'est pas modifié depuis `026b0f9` : `git diff 026b0f9 -- frontend` est vide.

## 5. Analyse statique et dépendances backend

| Contrôle | Commande | Résultat |
|---|---|---|
| Lint | `ruff check backend tools` (commande de la CI) | « All checks passed! », rc 0 |
| Formatage | `ruff format --check` sur les 4 fichiers Python modifiés ou ajoutés | « 4 files already formatted », rc 0 |
| Vulnérabilités | `pip-audit -r backend/requirements.txt --strict` (commande de la CI) | « No known vulnerabilities found », rc 0 |

## 6. Corpus des 8 originaux

| Run | Documents | Requêtes Interim | Violations de budget | Empreintes des originaux | Statut |
|---|---|---|---|---|---|
| run25e (verdict) | 8 sur 8 terminés | 0 (mémoire run24) | 0 | inchangées ×8 | `REVIEW_REQUIRED` ×8 |
| run25-live (supplémentaire) | 8 sur 8 terminés | 63, réservation max. 22 467 ≤ 32 768 | 0 | inchangées ×8 | `REVIEW_REQUIRED` ×8 |

## 7. Ce qui n'est pas testé

| Élément | État |
|---|---|
| Qualité de traduction par rapport à une référence humaine | `NOT_AVAILABLE` (aucune référence) |
| Qualification Qwen / vLLM privé | `NOT_AVAILABLE` (point de terminaison, tokeniseur et poids privés non fournis) |
| Fidélité des tableaux mesurée par le moteur | `NOT_MEASURED` (`no_real_table_detected` sur les 8 scans) |
| Tests de bout en bout du navigateur sur l'écran de revue | non exécutés |
| Jobs de CI d'acceptation privée et de publication manuelle | non déclenchés, hors de portée de la CI publique |

## 8. CI GitHub

Exécution [38248946774](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/38248946774)
(`pull_request`, PR brouillon #3), sur le SHA exact `c14197d3abb25903f66ff7d5511bd56f2c341212`. Ce SHA contient
le code `f4a84aaef38c7c7d` du verdict et les rapports. **Conclusion : `success`.**

| Job | Conclusion | Recoupement dans le journal |
|---|---|---|
| backend | success | **610 passed**, identique à la suite locale ; ruff « All checks passed! » ; pip-audit « No known vulnerabilities found » |
| backend-integration-and-migrations | success | 28 passed (PostgreSQL, Alembic) |
| frontend | success | 16 tests passed, 6 fichiers ; build OK ; npm audit : 0 vulnérabilité |
| container-and-manifest-validation | success | build des images ; npm audit : 0 vulnérabilité ; Helm : 1 chart linted, 0 failed |
| private-acceptance | skipped | gate privé conservé : il exige le corpus et ne s'exécute pas en CI publique |
| manual-release-gate | skipped | gate de publication manuel conservé |

La CI ne rejoue pas le corpus réel. Les résultats documentaires viennent des runs privés décrits dans
`RUN25_REGRESSION_REPORT.md`.
