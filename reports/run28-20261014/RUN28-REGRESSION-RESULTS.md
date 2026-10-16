# RUN28 — Résultats de non-régression

> Seuls les résultats exécutés et terminés sont cités. Les exécutions invalidées sont listées au § 5 et **ne sont pas comptées**.

## 1. Empreintes de l’arbre final

| Élément | Arbre testé par le corpus et les mesures | Arbre final (commit poussé) |
| --- | --- | --- |
| Code Python `backend/app` + `tools` (16 premiers caractères du SHA-256 de la liste triée des fichiers) | `25dbea622c921535` (commit local `38b73c0`, recalculé indépendamment) | `914d925722133d4d` |
| Règle de mesure (`ruler_fingerprint`, fermeture de 34 fichiers) | `08e998169c0dad9b` (recalculée à l’identique sur `38b73c0` ; RUN27 : `aa3883b0360e2dd6`) | `b827d913b8a71d88` |
| Tests Python `backend/tests` | — | `63e4fb3ac090d312` |
| Frontend `frontend/src` | `d9c0c0c36111b0ee` | `d9c0c0c36111b0ee` (inchangé) |

Entre l’arbre testé et l’arbre final, **3 fichiers de code diffèrent, uniquement par des commentaires** : `entities.py`, `service.py` et `language_evidence.py` (expurgation, § 7). Leur **AST Python est identique**, y compris les attributs de ligne et de colonne, et le nombre de lignes ne change pas. Les 90 autres fichiers sont identiques à l’octet près. Le comportement exécuté est donc strictement le même, ce qui explique les deux empreintes de règle. Le corpus verdict (run28e) et les mesures restent valides, sans relance ni appel Interim supplémentaire. La suite backend et le golden ont été **rejoués sur l’arbre final exact** (§ 3).

## 2. Exécutions du corpus (8 originaux, autorisation privée)

| Exécution | Durée | Groupes A/B/C | Empreinte code | Requêtes Interim | Originaux | Rôle |
| --- | --- | --- | --- | --- | --- | --- |
| run28 | 106 s | rc = 0 | `6718077cb37345dc` | 2 | inchangés | F35 + F37/F38/F38b + F39 |
| run28b | 107 s | rc = 0 | `3fc907a3d88146b9` | 1 | inchangés | + parcours A, UI (0 changement de statut, 0 page différente vs run28) |
| run28c | 105 s | rc = 0 | `36a96748992b86ba` | 1 | inchangés | + F40 (exactement 3 changements de statut, attendus) |
| run28d | 109 s | rc = 0 | `4a025e83db3ecc79` | 2 | inchangés | + F41 (passe + reprise ordinale), réservation max. 16 608 |
| **run28e (verdict)** | **104 s** | **rc = 0** | **`25dbea622c921535`** = fin | **0** | **inchangés** | + F42 : 8 × `TRANSLATION_MEMORY_REUSE_ONLY`, 0 changement de statut et 0 page différente vs run28d |

Chaque nouvelle exécution a suivi un changement de code. Aucune n’a été relancée pour « améliorer » un résultat. Toutes les requêtes sont restées sous la garde de 32 768 tokens (0 violation de budget).

## 3. Suites de tests (arbre final)

| Contrôle | Commande (identique à la CI) | Résultat |
| --- | --- | --- |
| Backend, périmètre CI exact (`unit`, `integration`, `e2e`, `regression`, `security`) | `PYTHONPATH=backend pytest … --junitxml` | **802 passed, 0 failed, 0 error, 0 skipped**, 71 avertissements, rc = 0, 216,6 s (JUnit : 802 tests). Code `914d925722133d4d` et tests `63e4fb3ac090d312` identiques au début et à la fin |
| Golden (8 cas) | `PYTHONPATH=backend pytest backend/tests/golden_dataset` | **8 passed, 0 failed, 0 skipped**, 63 avertissements, rc = 0, 1 163,3 s (JUnit : 8 tests). Code `914d925722133d4d` et tests `63e4fb3ac090d312` identiques au début et à la fin |
| Lint | `ruff check backend tools` | rc = 0 (« All checks passed! ») |
| Format | `ruff format --check` sur les 5 fichiers nouveaux, les 9 fichiers modifiés déjà formatés et les 12 fichiers expurgés | rc = 0 |
| Format (préexistant) | idem sur `routes.py`, `jobs.py`, `validation.py` | rc = 1, **déjà rc = 1 à `54bf5f2`** (non reformatés, voir RUN28-IMPLEMENTATION-CHANGES) |
| Frontend | `npm run typecheck && npm test && npm run build` | typecheck rc = 0 ; **30 passed** (8 fichiers) ; build rc = 0 |
| Dépendances | `npm audit --audit-level=high` ; `pip-audit -r backend/requirements.txt --strict` | 0 vulnérabilité ; aucune vulnérabilité connue |

Évolution : backend 719 (RUN27) → 802 (+83, soit exactement les 83 nouveaux tests RUN28 ; aucun test retiré). Angular 16 → 30 (+14). Une seule attente existante a été modifiée : `test_run18_regressions.py` exige désormais aussi la clé additive F41 `refusal_reused_not_resent`, avec l’égalité stricte conservée.

## 4. Tests ciblés et mutations

| Correctif | Fichier | Tests | Mutations (assertions qui échouent sur le code muté) |
| --- | --- | --- | --- |
| F35, F39 | `test_run28_regressions.py` | 32 : 24 F35 (dont 11 négatifs issus des faux positifs de la version rejetée) et 8 F39 | F39 : 4/4 détectées ; une 5e mutation est équivalente (le texte partiel est toujours réécrit par les chemins suivants) |
| F37, F38, F38b, F40 | `test_run28_render_regressions.py` | 15 | F37/F38/F38b : 6/6 ; F40 : 4/4 |
| Parcours A (XLSX/PPTX) | `test_run28_office.py` | 22 (falsifications détectées : formule, nom de feuille, commentaire, champ de numéro de diapositive ; cible absente ; changement inattendu ; dépôt refusé : macros, liens externes, connexions, objets incorporés, ActiveX, partie principale absente) | — |
| F41, F42 | `test_run28_ordinal_retry.py` | 14 (7 + 7, dont un cas d’échec HTTP pendant la reprise) | F41 : 5/6 ; la 6e est équivalente (toutes les sorties de la reprise réécrivent la cible) |
| Indicateurs UI | `indicators.spec.ts`, `document-detail.run28.spec.ts`, `review.page.spec.ts` | 12 + 1 (rendu DOM réel) + 1 | 5/5 (arrondi, inconnu → succès, dédoublonnage, approbation masquant les critiques, panneau retiré) |

Contre-épreuves : sans police condensée disponible, le bloc redevient `LAYOUT_OVERFLOW`. Un texte qui tient n’est jamais condensé. Un refus ordinal confirmé n’est jamais renvoyé.

## 5. Résultats invalidés ou remplacés (non comptés)

| Exécution | Résultat brut | Raison de l’exclusion |
| --- | --- | --- |
| Suite backend, chaîne F40 (code `36a96748992b86ba`) | 788 passed | code modifié ensuite (F41, F42) : résultat remplacé |
| Golden de la même chaîne | interrompu après 5 cas passés | arrêté volontairement au changement de code F41 |
| Suite backend, première chaîne sur le code final | 801 passed, **1 failed** | échec réel : attente stricte RUN18 ignorant la nouvelle clé de télémétrie F41. Comportement inchangé. Attente mise à jour, fichier 39/39. |
| Suite backend « run28c » (code `25dbea622c921535`, tests `d2b5f21530c04b75`) | 802 passed, 0 failed (224,6 s) | valide, mais remplacée : littéraux de tests modifiés ensuite (anti-fuite) |
| Suite backend « run28d » (code `25dbea622c921535`, tests `10d0e4907b5304c4`) | 802 passed, 0 failed, 71 avertissements (210,7 s) | valide, mais remplacée : expurgation des fragments hérités (§ 7) |
| Golden « run28c » (code `25dbea622c921535`, tests `d2b5f21530c04b75`) | 8 passed, 0 failed, 63 avertissements (1 209,8 s) | valide, mais remplacé par le golden sur l’arbre final (§ 3) |
| Suite backend « run28b » et golden associé | 792 passed, 1 failed, 9 errors | **incident de mon fait** : pendant l’exécution, j’ai supprimé le répertoire temporaire de pytest en libérant de l’espace disque. Toutes les erreurs portent sur les tests exécutés après la suppression. Résultats **invalides**, relancés avec un répertoire temporaire privé dédié (§ 3). |

## 6. Mesures

Règle RUN28 : 317 s. Règle RUN27 (arbre propre `54bf5f2`) : 336 s. Toutes les étapes (empreinte de règle, registre, planches, mesure, scorecard-1/2, vérifications 1/2) ont rc = 0. Le code retour non nul du script englobant venait uniquement de la commande d’affichage finale, mal formée. Aucune mesure n’a été relancée pour cette raison.

## 7. Confidentialité

### 7.1 Méthode

Deux scanners privés, non versionnés. Ils comparent le texte versionnable avec les textes OCR et les cibles de dix exécutions privées (RUN25 à RUN28e). Ils ont été appliqués **à tout le dépôt suivi**, pas seulement aux ajouts RUN28.

- **Principal** : 450 mots distinctifs, 10 979 4-grammes, 112 nombres ≥ 4 chiffres. Il cherche aussi les préfixes (≥ 8 hexadécimaux) des empreintes des 8 originaux, les chiffres de leurs noms de fichiers, les littéraux de l’autorisation privée, les motifs de secrets, les hexadécimaux ≥ 40, les noms `.pdf`, les chemins privés et les adresses électroniques.
- **Complémentaire** (ajouté en RUN28) : jetons alphanumériques mixtes (codes postaux, références), 2-grammes et 3-grammes contenant un mot rare.

### 7.2 Défaut du scanner hérité, corrigé

Le dépôt force la coloration (`color.ui=always`). La sortie de `git diff` contenait donc des séquences ANSI, et le scanner de RUN27 ne reconnaissait pas les en-têtes de fichiers. **Les lignes ajoutées aux fichiers déjà suivis n’étaient pas scannées** ; seuls les fichiers nouveaux l’étaient. Correctif : `git -c color.ui=never diff --no-color`. Après correction, 43 fichiers et 10 984 lignes sont réellement couverts pour RUN28.

### 7.3 Résultats

| Constat | Traitement |
| --- | --- |
| RUN28, commentaire de code : deux exemples de codes postaux **présents dans le corpus** ; deux commentaires citant le fragment d’identifiant du défaut MV-01 | trouvés **avant tout push** ; commentaires remplacés par des exemples inventés ; commit amendé (`d189972`) ; AST identique |
| RUN28, tests : deux mots néerlandais et un 4-gramme français présents dans le corpus | remplacés par des textes inventés |
| **Hérité (RUN ≤ 27, déjà poussé)** : fragments documentaires dans 10 fichiers de tests (intitulés de formulaire, un code postal, une phrase d’attestation, des clauses de congé et de délai, des intitulés de compte en espagnol et en français, une phrase arabe, un mot finnois, un fragment d’identifiant), 2 commentaires de code (un montant, une date et un artefact OCR), 2 rapports (une date de tampon, des intitulés) et 1 document (un chemin d’espace privé) | **tête de branche expurgée** (`c973e73`) : textes inventés, mêmes longueurs pour les littéraux liés à la géométrie, mêmes assertions (111/111 tests des fichiers touchés), code AST-identique |
| Génériques conservés | types de document (« attestation de travail », type néerlandais équivalent utilisé par le classifieur), formules de politesse, types d’identifiants (« cnss », « iban »), ordinaux, numéros fictifs réservés (plage Ofcom), identifiants de blocs, cellules et causes, empreintes SHA-256 de fichiers de code, compteurs et métriques |

Passe finale sur tout le dépôt suivi : il ne reste que les génériques ci-dessus. 0 préfixe d’empreinte d’original, 0 nom de fichier réel, 0 littéral d’autorisation, 0 motif de secret. Contrôle intégré de l’exporteur : 0 occurrence sur les 9 JSON. Aucun fichier binaire ajouté.

**Limite ouverte** : l’historique Git déjà poussé (branches RUN ≤ 27) contient encore les fragments hérités. Le commit d’expurgation ne corrige que la tête de branche. La réécriture de l’historique distant est une action destructive (réécriture et poussée forcée des branches partagées) : elle **n’a pas été faite** et attend une décision explicite (voir RUN28-OPEN-ISSUES, OI-16).

## 8. Commits et intégration continue

| Commit | Contenu | Auteur = committer |
| --- | --- | --- |
| `d189972` | RUN28 : code, tests, CI, Dockerfile, frontend (27 fichiers) | Hamza NORDINE (adresse noreply) |
| `c973e73` | expurgation des fragments hérités (15 fichiers, 0 changement d’AST) | Hamza NORDINE (adresse noreply) |
| `cb32d76` | rapports et exports anonymisés `reports/run28-20261014/` (16 fichiers) | Hamza NORDINE (adresse noreply) |

Branche `feature/run28-moteur-simplification-20261014`, empilée sur `feature/run27-score-remediation-20261013` (`54bf5f2`). Pull request en **brouillon**, aucune fusion.

**CI sur le commit poussé `cb32d76`** (exécution GitHub Actions n° 38595065645, événement `pull_request`, tentative 1, SHA de tête vérifié) : **succès**, 16:05:24Z → 16:10:36Z. Les décomptes ci-dessous sont lus dans les journaux des jobs, pas seulement dans leur statut.

| Job CI | Résultat | Preuve lue dans le journal |
| --- | --- | --- |
| `backend` | succès (186 s) | `ruff check backend tools` : « All checks passed! » ; pytest `unit + integration + e2e + regression + security` : **802 passed**, 71 avertissements (même décompte qu’en local) ; `pip-audit --strict` : « No known vulnerabilities found » |
| `backend-integration-and-migrations` | succès (133 s) | `alembic upgrade head` sur un vrai PostgreSQL : étape réussie, silencieuse par conception (aucune configuration de journalisation) ; RUN28 n’ajoute aucune migration ; tests d’intégration : **28 passed** |
| `frontend` | succès (36 s) | typecheck, tests (**8 fichiers, 30 passed**), build ; `npm audit --audit-level=high` : 0 vulnérabilité |
| `container-and-manifest-validation` | succès (120 s) | Compose validé ; `helm lint` : 1 chart, 0 échec ; `helm template` ; images API et frontend construites, avec installation effective de LibreOffice Writer, Calc et Impress dans l’image API |
| `private-acceptance`, `manual-release-gate` | ignorés | portes privée et manuelle, ignorées par conception comme en RUN27 : elles ne valent ni recette ni mise en production |

Le commit de complément qui ajoute ce paragraphe ne modifie que des rapports. Sa propre exécution CI est suivie séparément ; son résultat figure dans la pull request et non dans ce fichier, qui ne peut pas contenir le résultat de son propre commit.
