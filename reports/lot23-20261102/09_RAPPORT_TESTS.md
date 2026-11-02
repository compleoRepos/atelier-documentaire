# LOT 2.3 — Rapport de tests (livrable 9), état à la Phase A

| | |
|---|---|
| Lot / phase | LOT 2.3 — Phase A (audit et mesure de référence) |
| Base testée | branche `feature/ocr-surya-20261030`, tête `8351d83ffe0b` (PR brouillon, non fusionnée) ; **aucune modification** du code (contrôle d’empreinte du code et des tests identique avant et après : `044081dd76ff3690` / `18c5c9a842fa00ff`) |
| Date | 1er et 2 novembre 2026 |
| Objet | Établir l’état des tests **avant** toute correction, pour servir de référence de non-régression aux phases suivantes |

> Ce rapport décrit l’état des tests existants. Il ne contient encore **aucun test nouveau** : la Phase A interdit toute modification du code. Les tests nouveaux des phases B et C y seront ajoutés, avec leurs résultats avant et après correction.

## 1. Synthèse

| Ensemble | Résultat | Durée | Commentaire |
|---|---|---:|---|
| Analyse statique `ruff` (périmètre CI : `backend tools services`) | **OK** (0 signalement) | < 5 s | — |
| Suite backend (unitaires, intégration, bout en bout, régression, sécurité) | **1 031 réussis, 0 échec**, 2 ignorés, 1 échec attendu | 317,6 s | Les 3 cas non réussis sont expliqués au §3 |
| Rattrapage des 2 tests PostgreSQL ignorés (base jetable PostgreSQL 16, commande de la CI) | **3 réussis** (les 2 ignorés + le cas SQLite du même fichier) | 2,7 s | §7 |
| Golden documentaire (8 cas) | **8 réussis** | 1 252 s | Exécuté avec **Tesseract forcé** : il ne couvre pas le chemin Surya, qui est le chemin par défaut (§4) |
| Autotest du service Surya (sans réseau, sans poids) | **OK** | < 30 s | — |
| Front-end Angular (tests) | **8 fichiers, 30 tests réussis** | 32 s | Vérification de types et compilation : **non rejouées localement**, réussies dans la CI distante (§6) |
| Rendu Helm (`lint` + `template`) | **OK**, 11 objets | < 5 s | — |
| Configuration Compose | **OK** avec l’environnement exact de la CI | < 5 s | Échec dans le premier script local, faute de la variable `MINIO_KMS_SECRET_KEY` : erreur de **mon** script, pas un défaut du produit (§5) |
| Audit des dépendances Python (`pip-audit --strict`) | **ÉCHEC** : 39 avis sur 1 paquet (`pillow` 12.3.0) | — | Correctif disponible en 13.0.0 (version majeure) (§5) |
| Audit des dépendances front-end (`npm audit`, seuil *high*) | **ÉCHEC** : 27 vulnérabilités (21 modérées, 6 élevées) | — | Outillage de développement et de test uniquement (§5) |
| CI distante du commit audité | **ÉCHEC** | — | Uniquement à cause des deux audits de dépendances ; tests backend et front-end réussis (§6) |

**Lecture.** Le code audité est fonctionnellement vert. L’état n’est pourtant **pas livrable** : la CI échoue sur deux audits de dépendances, et le chemin OCR par défaut (Surya) n’a **aucun golden**.

## 2. Conditions d’exécution

- Machine : 6 vCPU, 23 Go de RAM, Python 3.12.3, Pillow 12.3.0, PyMuPDF 1.28.2.
- Commande de la suite : identique à l’étape `pytest` de la CI (`.github/workflows/ci.yml`), cœurs 0 à 3.
- Golden : exécuté **en parallèle** de la suite, sur un cœur dédié (cœur 5). Sa durée (1 252 s) n’est donc **pas** une mesure de performance.
- Front-end : copie temporaire du dossier `frontend` ; les dépendances installées proviennent d’un fichier de verrouillage **identique** à celui du commit audité (empreinte `55004c47`) ; aucun téléchargement.
- Audits de dépendances : bases de vulnérabilités **à la date du 1er novembre 2026**. Un audit rejoué plus tard peut donner un autre résultat sans aucun changement de code.

## 3. Tests ignorés et échec attendu

| Test | Statut | Raison | Conséquence |
|---|---|---|---|
| `test_glossary_entry_is_sent_when_followed_by_punctuation` | **échec attendu** (`xfail`) | Défaut connu **F-L2-03** : une entrée de glossaire client suivie d’une ponctuation n’est pas envoyée au moteur. Le test documente le défaut dans un fichier gelé. | Doit devenir un test **réussi** après la correction F-L2-03 (Phase B ; ordre à valider, livrable 1, §11) |
| `test_0004_adds_only_lot2_tables_and_downgrades_to_exact_0003[postgresql]` | **ignoré** | Exige la variable `RAG_TEST_POSTGRES_URL` (PostgreSQL réel) ; absente de la commande de la suite | Rattrapé séparément sur une base jetable (§7) |
| `test_bm25_publication_search_rollback_and_isolation_on_postgresql` | **ignoré** | Même raison | Rattrapé séparément (§7) |

Répartition des 1 034 cas collectés : unitaires 954, intégration 72, bout en bout 3, régression 2, sécurité 3. Avertissements : 95 occurrences de 4 avertissements de dépréciation (3 `DeprecationWarning`, 1 `StarletteDeprecationWarning`), sans échec.

## 4. Golden : ce qu’il prouve et ce qu’il ne prouve pas

Le golden compare 8 cas documentaires à des sorties de référence. Il passe (8 sur 8). Mais la configuration de test (`conftest.py`) **force Tesseract**, afin que les références historiques restent reproductibles. Conséquences :

- il prouve que le **mode Tesseract explicite** ne régresse pas ;
- il ne prouve **rien** sur le chemin **Surya**, qui est le moteur OCR **par défaut** depuis la bascule demandée. Or c’est sur ce chemin que le défaut critique de reconstruction **D-REC-02** a été mesuré au LOT 2.2 (une colonne de tableau fusionnée, une ligne traduite absente du PDF final) ;
- dans la CI hébergée, le golden ne tourne **jamais** : il est réservé à un job auto-hébergé (`private-acceptance`), sauté dans la CI distante du commit audité.

Constat **D-REC-01** (reconduit) : il faut un golden sur le chemin Surya avant toute décision de production.

## 5. Échecs d’audit et faux échec

**`pip-audit` — Pillow 12.3.0 (épinglé dans `backend/requirements.txt`, ligne 11).** 39 avis publiés, corrigés en 13.0.0. Le passage à 13.0.0 est une **version majeure** de la bibliothèque qui produit les images de page et une partie des rendus. Il peut donc modifier des pixels du golden. Ce correctif n’est pas fait en Phase A (aucune modification de code). Il doit être fait en Phase B, golden rejoué et différences de pixels qualifiées, et non masqué par une exception d’audit.

**`npm audit` — 27 vulnérabilités (21 modérées, 6 élevées).** Elles touchent l’outillage de développement et de test (`@angular/cli`, `@angular/build`, `vitest`, `sigstore`, `@modelcontextprotocol/sdk`, `body-parser`, `ip-address`, `minimatch`, `glob`, `fast-uri`), pas le code servi au navigateur. Cela réduit le risque en production sans l’annuler : ces outils s’exécutent sur les postes de développement et dans la CI.

**Configuration Compose — faux échec.** Le premier contrôle local a échoué faute de la variable `MINIO_KMS_SECRET_KEY`, qu’exige le stockage chiffré. Rejoué avec l’environnement exact de la CI (lignes 140 à 148 du fichier de CI), il réussit. L’erreur venait de mon script, pas du produit.

**Remarque mineure (environnement local, pas le dépôt).** Une ancienne image MinIO locale (`atelier-documentaire-minio:source-pinned`, du 7 octobre) contient une archive Go au lieu d’un exécutable (« exec format error »). L’image réellement produite par le `Dockerfile` du dépôt, inchangé, est saine. Le binaire construit s’annonce `DEVELOPMENT.GOGET` : la version n’est pas inscrite à la compilation, ce qui gêne la traçabilité.

## 6. CI distante du commit audité

Exécution 41151865475, conclusion **ÉCHEC** :

| Job | Résultat | Détail |
|---|---|---|
| `backend` | échec | `ruff` OK ; `pytest` **réussi** (comptes détaillés : §2) ; échec à l’étape `pip-audit --strict` (Pillow) |
| `frontend` | échec | vérification de types, tests et compilation **réussis** ; échec à l’étape `npm audit` (seuil *high*) |
| `backend-integration-and-migrations` | **réussi** | migrations Alembic sur un PostgreSQL 16 réel, tests d’intégration, et tests PostgreSQL du LOT 2 (mêmes fichiers que le rattrapage du §7) |
| `container-and-manifest-validation` | sauté | dépend du job `backend` |
| `private-acceptance` (golden) | sauté | job auto-hébergé |
| `manual-release-gate` | sauté | ne s’exécute que sur un déclenchement manuel de mise en production |

La CI de l’avant-dernier commit de la branche échouait de la même manière : ces échecs sont **antérieurs** au LOT 2.3.

## 7. Rattrapage des tests PostgreSQL ignorés

Base **dédiée et jetable** (`lot23_ragtest`) sur un PostgreSQL 16 temporaire, distincte de la base de mesure (un des tests descend les migrations). Commande identique à l’étape CI correspondante, même commit `8351d83ffe0b`, 0 modification locale. Base supprimée après l’exécution.

| Test | Résultat | Durée |
|---|---|---:|
| `test_0004_adds_only_lot2_tables_and_downgrades_to_exact_0003[sqlite]` | réussi | 0,56 s |
| `test_0004_adds_only_lot2_tables_and_downgrades_to_exact_0003[postgresql]` | **réussi** | 1,00 s |
| `test_bm25_publication_search_rollback_and_isolation_on_postgresql` | **réussi** | 0,44 s |

Total : **3 réussis**, 10 avertissements de dépréciation, 2,72 s. Les deux tests ignorés par la suite (§3) passent donc sur un PostgreSQL réel.

**Défaut de mon outillage, déclaré.** La première tentative a échoué avant même de lancer `pytest` : mon script appelait `psql` dans le conteneur sans préciser le port, et visait donc le port par défaut 5432, alors que la base temporaire écoute sur 55432. Le produit n’est pas en cause. Le script a été corrigé, puis rejoué.

## 8. Tests à créer dans les phases suivantes (rappel de la consigne)

Aucun n’existe aujourd’hui. Ils seront ajoutés en Phase B avec leurs résultats avant et après correction : non-régression F-L2-02, F-L2-03 et D-DET-02 ; tests unitaires DICE ; tests de cohérence des valeurs financières ; golden sur le chemin Surya (D-REC-01) ; tests de performance automatisés ; tests de concurrence ; tests d’arrêt et de reprise des tâches Celery.
