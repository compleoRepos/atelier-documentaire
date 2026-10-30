# DICE — Phase 0 : état initial du dépôt et plan du LOT 1

Date : 30/10/2026. Les mesures de ce document ont été exécutées entre 13:28 et 13:38 UTC. Aucun fichier du dépôt n'a été modifié pendant la Phase 0.

## 1. État réel du dépôt

| Élément | Constat |
|---|---|
| Dépôt | `compleoRepos/atelier-documentaire` (public) |
| Branche | `feature/run29-correction-bout-en-bout-20261016` |
| Commit local | `d8bb59ab1e2b0ee4363feba90df6470ff01f6741` |
| Commit distant (`ls-remote`) | identique |
| Copie de travail | propre : 0 fichier modifié, 0 commit local en avance |
| Branches plus récentes | aucune (d8bb59a est le commit le plus récent du dépôt) |
| Machine | 6 CPU, 23 Go RAM, 14 Go de disque libres, PostgreSQL 16 local disponible, `helm` disponible |
| Outils | Python 3.12.3, ruff 0.16.10, pytest 9.1.1, Pillow 12.3.0, Angular 21.2.25 (build/cli 21.2.26), vitest 4.1.11 |

Le dépôt correspond exactement à la version auditée dans le LOT 0.

## 2. Vérifications exécutées

| Vérification | Commande | Résultat réel |
|---|---|---|
| Empreinte de règle | `tools/recette/ruler_fingerprint.py` | `b0b0261eaabecda8` (`ruler-fingerprint-1`, 29 fichiers produit, 5 fichiers outils), identique à l'audit |
| Lint | `ruff check backend tools` | rc=0 |
| Suite CI backend | `pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security` | rc=0 : **873 réussis, 0 échec, 0 ignoré**, 225,5 s |
| Collecte complète | `pytest backend/tests --collect-only` | 881 tests |
| Contrat OpenAPI | `create_app().openapi()` avec la configuration par défaut | 18 chemins, empreinte `053a70246afd3cc9`, aucun module `app.rag` chargé |
| Audit Python | `pip-audit -r backend/requirements.txt --strict` | rc=1 : 39 vulnérabilités, **toutes sur pillow 12.3.0**. Seule version corrective : 13.0.0 (majeure) |
| Audit frontend | `npm audit --audit-level=high` | rc=1 : 12 vulnérabilités (6 hautes, 6 moyennes) |

## 3. Écarts avec l'audit LOT 0

1. **Nombre de tests : 881 collectés au lieu de 874.** Ce n'est pas une évolution du code. Le test golden est paramétré par le catalogue local des 8 originaux confidentiels (fichier ignoré par Git). La copie d'audit, extraite par `git archive`, ne contenait pas ce catalogue : le golden n'y donnait qu'un cas. Ici il en donne 8 (DOC-001 à DOC-008). La suite CI exacte compte 873 tests et le golden 8 (873 + 8 = 881). Le critère « 874 tests existants » se lit donc ainsi : 873 tests de la suite CI plus les cas golden, tous exécutés.
2. **Code et numéros de ligne :** aucun écart. Les points d'ancrage de l'audit sont confirmés : appel de la traduction à `jobs.py:470` ; ordre de retrait du contexte à `service.py:837-844` (`memory`, `entities`, `document`, `document_memory`, `terms`, `decisions`, `previous`) ; canaux `document_memory` et `country_context` à `builder.py:279-383`.
3. **CI au commit d8bb59a** (exécution 40723107568, déclenchement manuel) : en échec **uniquement** sur `pip-audit` (job backend) et `npm audit` (job frontend). Ruff, les tests backend, les tests d'intégration sur PostgreSQL et les migrations, ainsi que les tests frontend, sont verts. Le job conteneurs est ignoré parce qu'il dépend des deux jobs rouges. Cela confirme le constat de l'audit.

## 4. Chantier de maintenance séparé (section 13)

- **Échecs reproduits localement :** voir le tableau 2.
- **Dépendances concernées :**
  - Python : `pillow==12.3.0`, ligne 11 de `backend/requirements.txt`.
  - Frontend :
    - dépendances directes `@angular/build` et `@angular/cli` 21.2.26, corrigées en 21.2.29 (correctif) ;
    - `vitest` 4.1.11, corrigé en 4.1.12 ;
    - dépendances transitives `body-parser`, `fast-uri`, `ip-address`, `qs`, corrigées par `npm audit fix` sans `--force` ;
    - `undici`, `vite`, `zod` et `@modelcontextprotocol/sdk` sont corrigées par les mises à jour directes.
- **Mises à jour minimales proposées :**
  - `pillow 13.0.0`, version majeure et seule version corrective ;
  - les trois correctifs frontend ci-dessus ;
  - aucune autre dépendance.
- **Vérification d'impact en cours** sur une branche et un worktree séparés (`maintenance/audits-securite-20261030`, base d8bb59a) :
  - suite CI complète ;
  - golden des 8 originaux comparé pixel à pixel et JSON par JSON entre Pillow 12.3.0 et 13.0.0 ;
  - tests et build frontend, taille des bundles.
- **Indépendance vis-à-vis du LOT 1 :** le LOT 1 est construit sur d8bb59a, sans ce chantier. La preuve « DISABLED identique » reste donc propre. Les deux audits resteront rouges sur la branche LOT 1 tant que la maintenance n'aura pas été validée : c'est un écart préexistant documenté, pas une conséquence du RAG.

## 5. Risques identifiés

| N° | Risque | Mesure prévue |
|---|---|---|
| R1 | La migration `0003_rag` déplace la tête Alembic. Avec `AUTO_CREATE_SCHEMA=false`, l'application refuse de démarrer tant que `alembic upgrade head` n'a pas été exécuté, même en DISABLED. | La procédure actuelle exécute déjà cette commande avant chaque déploiement (`docs/deploiement.md` § 5.5/6.6). Le guide d'installation RAG le rappellera. Le rollback principal consiste à repasser en DISABLED, sans toucher à la base. Le downgrade vers 0002 ne se fait qu'avec un retour au code d8bb59a. |
| R2 | Le moteur hors ligne ignore `document_memory`. ASSISTED n'a donc aucun effet sur la traduction en mode hors ligne. | Ce sera documenté. L'évaluation A/B/C du LOT 2 exigera un moteur génératif privé. Les poids gpt-oss locaux ont été supprimés le 28/10 (12 Go à retélécharger, 14 Go libres). |
| R3 | Le constructeur gelé sélectionne le contexte par sous-chaîne : des entrées RAG peuvent apparaître dans des lots où le terme est absent. | Le budget RAG est mesuré requête par requête, avec le vrai tokenizer, avant toute injection. |
| R4 | Le contrôle d'éviction doit refléter le vrai prompt. | Une exécution à blanc du service gelé, avec un transport HTTP factice (aucun appel réseau, aucun appel modèle), compare le contexte de chaque requête avec et sans RAG. En cas de doute, le RAG est abandonné et les options restent inchangées. Coût CPU mesuré. |
| R5 | En SHADOW avec Celery, si aucun worker ne consomme la file `rag`, les messages s'accumulent. | Le worker `rag` sera déclaré dans un profil Compose et une valeur Helm désactivée par défaut, avec une expiration des tâches. L'état sera visible dans `/api/rag/status`. |
| R6 | La CI restera rouge sur les deux audits préexistants. | Écart documenté ; le correctif est proposé séparément. |
| R7 | Le test de garde de l'empreinte de règle échouera dès qu'une évolution légitime du produit modifiera la fermeture. | C'est voulu : toute évolution de l'empreinte doit être validée. |
| R8 | Le principe des quatre yeux (le validateur doit être différent de l'auteur de la version) peut bloquer une équipe d'une seule personne. | Règle prudente adaptée au bancaire, documentée. Elle ne s'applique qu'au module RAG. |

## 6. Plan exact du LOT 1

**Branche :** `feature/rag-lot1-socle-20261030`, base d8bb59a. PR brouillon, sans fusion.

1. **Configuration** : ajout dans les Settings existants de champs RAG désactivés par défaut :
   - `rag_mode` (DISABLED, SHADOW, ASSISTED, ACTIVE) ;
   - `rag_admin_enabled` ;
   - les budgets ASSISTED (800) et ACTIVE (1 500) ;
   - le nombre maximal d'entrées.

   Validation au démarrage. Toute variable `TRANSLATOR_RAG_*` inconnue est refusée, pour qu'aucune variable ne soit ignorée en silence.
2. **Modes :** mode effectif = minimum(mode global, mode maximal du tenant). Le mode maximal d'un tenant vaut DISABLED par défaut, ce qui laisse inchangés les tenants existants. Un tenant ne peut pas dépasser le mode global : l'API refuse et le calcul borne.
3. **Données :** migration `0003_rag` qui crée **11 tables `rag_*` uniquement** :
   - référentiels ;
   - versions ;
   - entrées terminologiques ;
   - textes réglementaires ;
   - passages réglementaires ;
   - équivalences de notions ;
   - événements de validation ;
   - contexte documentaire ;
   - paramètres par tenant ;
   - affectations de rôles ;
   - journal des recherches.

   Isolation par `tenant_id`. Les référentiels communs (`tenant_id` NULL) sont en lecture seule pour les tenants. Le downgrade supprime ces 11 tables et elles seules. Migration compatible SQLite et PostgreSQL.
4. **Module `backend/app/rag/` :**
   - `config` ;
   - `models` ;
   - `schemas` ;
   - `core` : moteur, recherche exacte normalisée avec cache isolé, priorités, politiques, construction du contexte ;
   - `terminology/normalizer` : normalisation générique, la normalisation arabe arrivant au LOT 2 ;
   - `resolver/document_context` : contexte déclaré, sans inférence avant le LOT 3 ;
   - `storage` : dépôt de données filtré par tenant, versionnement et validation ;
   - `integration/augment_options` ;
   - `api` : routes et administration ;
   - `workers` : file Celery `rag` ;
   - `audit` : journal sans texte, rapport d'explication.

   **Aucun import** vers les 29 fichiers de la fermeture de mesure.
5. **Intégration :**
   - Dans `run_translate`, un seul appel conditionnel est ajouté juste avant `_call_translate`. L'import est paresseux et l'appel n'a lieu que si le mode n'est pas DISABLED.
   - `augment_options` renvoie l'objet d'options lui-même, inchangé, en DISABLED et en SHADOW.
   - En ASSISTED et ACTIVE, il renvoie une copie dans laquelle seuls `document_memory.terminology`, `document_memory.translation_decisions` (ACTIVE) et `country_context` (ACTIVE) sont ajoutés.
   - `glossary`, `memory`, `terms` et `reference` ne sont jamais touchés. Une entrée RAG qui recoupe le glossaire ou la mémoire du bloc est écartée.
6. **Sonde budget et éviction** (`backend/app/application/rag_bridge.py`, hors `app.rag`) :
   - Exécution à blanc du service gelé, avec transport factice : aucun réseau, aucun modèle.
   - Mesure, par requête, des jetons RAG avec le tokenizer du moteur, et contrôle qu'aucun élément de contexte existant ne disparaît.
   - En cas de dépassement, les résultats RAG sont réduits ; en dernier recours, le RAG est abandonné.
   - Le plafond de 40 blocs par lot n'est pas modifié.
7. **SHADOW :**
   - Avec Celery, la tâche est envoyée dans la file `rag` et ne transporte que des identifiants, aucun texte.
   - Sans Celery, un exécuteur d'arrière-plan à un seul fil est utilisé.
   - Les erreurs sont absorbées. Aucune influence sur la traduction, prouvée par l'identité des options et des sorties.
8. **API :**
   - `/api/rag/status`, `/api/rag/documents/{id}/context` (GET/PUT), `/api/rag/documents/{id}/explanation` et `/api/rag/search` sont montées seulement si le mode n'est pas DISABLED.
   - `/api/rag-admin/*` n'est monté que si `rag_admin_enabled=true` : paramètres du tenant, rôles, référentiels, versions, validation, publication, historique.
   - Les rôles RAG sont gérés dans une table indépendante : administrateur RAG, responsable terminologique, responsable juridique (seul habilité à publier un texte réglementaire), lecteur.
   - Aucune publication automatique.
9. **Lanceur de recette `tools/rag_corpus_run.py`** : utilise exactement la même fonction `augment_options` et la même sonde que `jobs.py`. Il produit un manifeste (mode, empreintes) et refuse toute réutilisation de cache hors DISABLED.
10. **Déploiement :** worker `rag` en profil Compose `rag` et en valeur Helm `rag.worker.enabled=false`. Le rendu par défaut reste identique, vérifié avec `docker compose config` et `helm template`.
11. **Documentation et rapports :**
    - dans `docs/rag/` : architecture, installation avec migration et rollback, administration, démonstration ;
    - dans `reports/rag-lot1-20261030/` : registre des changements, tests, sécurité, performance, non-régression.

## 7. Fichiers qui seront touchés

**Fichiers existants modifiés.** Chacun sera justifié dans le registre des changements.

| Fichier | Modification prévue |
|---|---|
| `backend/app/core/settings.py` | Champs RAG à valeurs par défaut désactivées et validation |
| `backend/app/application/jobs.py` | Un appel conditionnel avant `_call_translate` |
| `backend/app/main.py` | Montage conditionnel des routeurs RAG |
| `compose.yaml` | Service `worker-rag` sous le profil `rag` |
| Chart Helm (`values.yaml`, nouveau gabarit) | Worker `rag` désactivé par défaut |
| `.env.example` | Variables documentées, valeurs désactivées |

**Fichiers non modifiés :**
- les trois fichiers gelés (`builder.py`, `service.py`, `pipeline.py`) et les 26 autres fichiers de la fermeture ;
- les tests et migrations existants ;
- le frontend (le back-office arrive au LOT 2) ;
- `docs/openapi.json`, car le contrat existant est inchangé en DISABLED ;
- les dépendances : aucune nouvelle dépendance au LOT 1.

**Fichiers créés :**
- `backend/app/rag/**` ;
- `backend/app/application/rag_bridge.py` ;
- `backend/migrations/versions/0003_rag.py` ;
- `tools/rag_corpus_run.py` ;
- `backend/tests/unit/test_rag_*.py` ;
- `backend/tests/integration/test_rag_postgres_migration.py` ;
- `docs/rag/*.md` ;
- `reports/rag-lot1-20261030/*.md`.

## 8. Tests qui seront exécutés

1. Suite CI complète (873) et 8 golden, sur l'arbre final.
2. Nouveaux tests :
   - DISABLED identique : options, sorties, OpenAPI `053a70246afd3cc9`, aucun module `app.rag` importé (contrôle en sous-processus) ;
   - empreinte `b0b0261eaabecda8` ;
   - absence d'import entre `app.rag` et la fermeture, dans les deux sens ;
   - migration upgrade, downgrade, upgrade sur SQLite et sur PostgreSQL 16 réel, avec contrôle que les 9 tables existantes ne bougent pas ;
   - isolation des tenants : base, API, cache, journal ;
   - SHADOW sans influence et sans ralentissement ;
   - aucune injection dans `glossary` ;
   - aucune éviction, avec un tokenizer réel en mémoire et un transport factice ;
   - lanceur de recette ;
   - rôles et validation ;
   - journal sans texte ;
   - injection de prompt.
3. Preuve corpus : les 8 originaux, en DISABLED sur l'arbre LOT 1 comparé à d8bb59a, artefacts JSON et rendus pixel par pixel, puis SHADOW comparé à DISABLED.
4. Rendu identique par défaut, vérifié avec `ruff`, `docker compose config` et `helm template`.
5. Performance : latence de `run_translate` en DISABLED et en SHADOW, mesurée sur des exécutions répétées.

Le LOT 2 (imports, normalisation arabe, BM25, back-office Angular, corpus A/B/C) ne commencera qu'après validation explicite du LOT 1. Le LOT 3 se limite aux tables préparées.
