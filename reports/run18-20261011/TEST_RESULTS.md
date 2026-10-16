# RUN18 — Résultats des tests

Tous les chiffres viennent de journaux d'exécution réels (conservés hors Git). Empreintes : SHA-256 des
sources Python, tronqué à 16 caractères, calculé au début **et** à la fin de chaque exécution.

| Empreinte | Périmètre | Valeur |
|---|---|---|
| code | `backend/app`, `tools` | `4d4956273c97d866` (code du verdict `run24`, inchangé depuis) |
| code + tests | `backend/app`, `tools`, `backend/tests` | `a90c55039b0d56a8` (état committé) |

## 1. Suite technique backend (périmètre CI)

Commande (identique à la CI) :
`PYTHONPATH=backend pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security`

| Exécution | Code | Résultat | Durée |
|---|---|---|---|
| Code initial `ebb09eb`, avant toute modification | initial | 549 passed, 0 failed | 220,9 s |
| Verdict run24 | `4d4956273c97d866` | 591 passed, 0 failed, 0 skipped | 207,9 s |
| **État final committé** | `4d4956273c97d866` / tests `a90c55039b0d56a8` | **591 passed, 0 failed, 0 skipped** | 220,1 s |

Écart 549 → 591 (+42) : `test_run18_regressions.py` +39, `test_recette_render_outcome.py` +2,
`test_inflated_line_box_final.py` +1 (test adapté à F1). Aucun test existant supprimé ; deux tests existants
adaptés à F1/F2 (`test_inflated_line_box_final.py`, `test_form_structure_guard_final.py`), leur intention
est inchangée.

Entre le verdict et l'état final, seuls des tests ont changé (docstrings et deux chaînes synthétiques
neutralisées par l'audit anti-fuite, §6) ; le code est identique (même empreinte).

## 2. Tests ajoutés par run18

| Fichier | Tests | Couverture |
|---|---|---|
| `backend/tests/unit/test_run18_regressions.py` | 39 | F1, F2b, F2, F3, F4, F5, F7, F9–F13b, F15–F19, mémoire de traduction ; données entièrement synthétiques |
| `backend/tests/unit/test_recette_render_outcome.py` | 2 | mesure indépendante M1 (croissance à gauche, débordement, troncature réelle) |

Plusieurs tests ont été vérifiés **en échec sur l'ancien code** (contre-épreuve) avant correction : F17 (case
vide sur ligne OCR gonflée), F19 (montée sur la ligne voisine), M1 (ancienne zone de recherche).

## 3. Contrôles statiques et dépendances

| Contrôle | Résultat |
|---|---|
| `ruff check backend tools` (ruff 0.16.10, commande CI) | All checks passed |
| `ruff format --check` sur les 16 fichiers Python touchés | 16 files already formatted |
| `git diff --check` | aucun défaut d'espaces |
| `pip-audit -r backend/requirements.txt` (avec `wordfreq==3.1.1`) | No known vulnerabilities found |

## 4. Frontend (inchangé par run18)

| Contrôle | Résultat |
|---|---|
| `npm run typecheck` | rc 0 |
| `npm test` (Vitest 4.1.11) | 6 fichiers, **16 passed** |
| `npm run build` | rc 0 (avertissement préexistant NG8107, non bloquant) |
| `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |

## 5. Corpus réel (8 originaux, autorisation propriétaire hors Git)

| Contrôle | Résultat |
|---|---|
| Passage verdict `run24` | 8 / 8 documents terminés ; 0 requête (mémoire F16) ; 0 violation de budget |
| Intégrité des originaux | SHA-256 identique avant / après, 8 / 8, à chaque passage |
| Pages | 31 / 31 conservées |
| Statut qualité | 8 × `REVIEW_REQUIRED` (aucun PASS) |
| Chaîne Interim (run19, run21, run22) | 61 requêtes, réservation maximale 22 467 ≤ 32 768, 0 violation |

## 6. Audit anti-fuite avant commit

Exécuté sur toutes les lignes ajoutées et tous les fichiers nouveaux (27 fichiers), par comparaison privée
avec les données réelles :

| Contrôle | Résultat |
|---|---|
| Fichiers binaires | 0 |
| Noms de fichiers originaux, SHA-256 réels, chemins privés, autorisation | 0 |
| Secrets (motifs de clés, valeurs des variables d'environnement sensibles) | 0 |
| Séquences de 4 mots du texte OCR/traduit réel | 3 restantes, toutes génériques (« travaille à temps plein » dans un test de langue, deux tournures grammaticales dans les rapports) |
| Fragments issus du contenu réel cités dans le code, les tests ou les rapports | 9 neutralisés (5 docstrings, 2 chaînes de test, 2 passages du rapport de causes : lectures OCR d’options, fragment de numéro, titre de clause), tests relancés |

## 7. Jeu golden

`backend/tests/golden_dataset` sur le jeu golden **local** du bac à sable (8 originaux, ignorés par Git ;
seuls 4 `.gitkeep` vides sont suivis). Le test exécute pour chaque document une **analyse complète neuve**
(OCR compris, code courant), puis une traduction avec le moteur `offline` (aucun réseau), et vérifie :
nombre et numérotation des pages, existence du candidat, statut `REVIEW_REQUIRED`, `translation_score`
nul, statut de référence `not_evaluated` / `not_available` (aucune référence humaine approuvée).

| Exécution | Code | Résultat | Durée |
|---|---|---|---|
| Premier essai (limite 900 s) | `4d4956273c97d866` | interrompu par la limite après 6 cas (rc 124) : **non-résultat** | 900 s |
| **Exécution complète** | `4d4956273c97d866` (début et fin) | **8 passed**, 0 failed, 0 skipped | 1 163,8 s |

Portée : contrôle technique de bout en bout ; il ne mesure ni la fidélité de mise en page ni la qualité de
traduction et ne peut pas produire de PASS de recette.

## 8. CI GitHub

Exécution [38176137547](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/38176137547)
(`pull_request`, PR #2 brouillon) sur le SHA exact `10693039218af42a39e70f1f61cc61510e192c29`
(code `e3714b6` + rapports), dont l'arbre a les empreintes `4d4956273c97d866` / `a90c55039b0d56a8` :
**success**.

| Job | Conclusion | Recoupement dans le journal CI |
|---|---|---|
| backend | success | ruff « All checks passed » ; **591 passed** (identique au local) ; pip-audit sans vulnérabilité |
| frontend | success | 6 fichiers, **16 tests passed** ; npm audit 0 vulnérabilité |
| backend-integration-and-migrations | success | PostgreSQL / Alembic : **28 passed** |
| container-and-manifest-validation | success | images, Compose, Helm ; audit 0 vulnérabilité |
| private-acceptance | **skipped** | exige l'infrastructure privée : ce n'est pas un PASS |
| manual-release-gate | **skipped** | porte manuelle, aucun déploiement automatique |

Les commits postérieurs à ce SHA ne modifient que des rapports.

## 9. Ce qui n'a pas été exécuté

* Portes CI `private acceptance` / `manual release` : elles exigent le jeu golden privé et les roues hors
  ligne de l'infrastructure privée ; non disponibles hors de cette infrastructure (SKIPPED, ce n'est pas
  un PASS).
* Aucun test avec le modèle privé Qwen/vLLM (point de terminaison non disponible) ; aucune mesure de
  qualité de traduction contre une référence humaine (aucune référence).
