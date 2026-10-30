# DICE (RAG) — rapport du LOT 1 : socle technique

> Branche `feature/rag-lot1-socle-20261030`, base `d8bb59a` (tête RUN29).
> Date : 2026-10-30. Toutes les valeurs ci-dessous proviennent d'exécutions
> réelles sur l'arbre final du LOT 1, sauf mention contraire.

## 0. Verdict

| Critère GO/NO-GO (consigne §16) | Preuve | Résultat |
|---|---|---|
| DISABLED strictement identique | aucun module `app.rag` importé, options de traduction identiques, aucune route ni table `rag_*`, OpenAPI identique octet pour octet, golden des 8 originaux comparé à la base | **atteint** |
| Empreinte inchangée | empreinte de règle `b0b0261eaabecda8…` identique (29 fichiers produit, 5 outils) | **atteint** |
| Tests existants | 873 réussis sur 873 du périmètre CI (même nombre qu'en Phase 0) ; golden 8/8 | **atteint** (voir §5.4 pour 874) |
| Nouveaux tests | 51 réussis sur 51 | **atteint** |
| Migration | upgrade, cohérence modèle/schéma, downgrade et ré-upgrade sur SQLite et PostgreSQL 16 | **atteint** |
| Aucun composant gelé modifié | 4 fichiers existants modifiés par **ajout seul** ; aucun fichier de la fermeture de mesure touché ni chargé par `app.rag` | **atteint** |
| Aucune fuite inter-tenant | tests d'isolation API et dépôt, contrôle PostgreSQL | **atteint** (sur les cas testés) |
| SHADOW ne ralentit pas le chemin critique | coût mesuré 0,25 ms (p50) ; recherche ralentie de 1 s sans effet sur le chemin critique | **atteint** |

**Décision proposée : GO pour le LOT 1, en mode DISABLED par défaut.** Le LOT 1
ne prouve **aucun gain de qualité** de traduction : il n'injecte rien tant que
des référentiels n'ont pas été constitués et validés par des humains, et la
mesure des gains sur corpus annoté relève du LOT 2. La relecture humaine des
traductions reste obligatoire quel que soit le mode.

Écart préexistant, hors périmètre du LOT 1 : la CI de la base `d8bb59a` échoue
sur les audits de dépendances (Pillow 12.3.0 : 39 avis ; dépendances de
construction Angular : 12 avis npm). Le LOT 1 n'ajoute ni ne modifie aucune
dépendance ; la correction est livrée dans une branche de maintenance séparée.

## 1. Code source

Branche `feature/rag-lot1-socle-20261030`. Documentation :
`docs/rag/ARCHITECTURE.md`, `docs/rag/INSTALLATION-ADMINISTRATION.md`.

## 2. Fichiers créés (57)

| Fichier | Lignes | Rôle |
|---|---:|---|
| `backend/app/rag/__init__.py` | 8 | paquet (aucun import) |
| `backend/app/rag/config.py` | 80 | modes, mode effectif, budgets |
| `backend/app/rag/models.py` | 336 | 11 tables `rag_*` |
| `backend/app/rag/schemas.py` | 85 | corps de requête validés (champs inconnus refusés) |
| `backend/app/rag/bootstrap.py` | 20 | création des seules tables `rag_*` (mode auto) |
| `backend/app/rag/api/__init__.py` | 1 | paquet |
| `backend/app/rag/api/deps.py` | 36 | rôles, conversion des refus en codes HTTP |
| `backend/app/rag/api/routes.py` | 143 | `/api/rag/*` |
| `backend/app/rag/api/admin_routes.py` | 270 | `/api/rag-admin/*` |
| `backend/app/rag/api/mount.py` | 26 | montage conditionnel |
| `backend/app/rag/audit/__init__.py` | 1 | paquet |
| `backend/app/rag/audit/provenance.py` | 55 | journal sans texte, empreinte HMAC |
| `backend/app/rag/audit/explanation.py` | 105 | explication par document |
| `backend/app/rag/core/__init__.py` | 1 | paquet |
| `backend/app/rag/core/retrieval.py` | 256 | instantanés publiés, cache isolé, n-grammes |
| `backend/app/rag/core/ranking.py` | 165 | priorités, ambiguïtés, ordre déterministe |
| `backend/app/rag/core/context_builder.py` | 118 | format des canaux gelés, rejet des textes dangereux |
| `backend/app/rag/core/policies.py` | 61 | canaux par mode, réduction bornée |
| `backend/app/rag/core/engine.py` | 239 | orchestration |
| `backend/app/rag/integration/__init__.py` | 1 | paquet |
| `backend/app/rag/integration/augment_options.py` | 265 | point d'intégration unique |
| `backend/app/rag/resolver/__init__.py` | 1 | paquet |
| `backend/app/rag/resolver/document_context.py` | 64 | filtres du contexte déclaré |
| `backend/app/rag/storage/__init__.py` | 1 | paquet |
| `backend/app/rag/storage/repository.py` | 371 | accès filtré par tenant |
| `backend/app/rag/storage/versioning.py` | 364 | versions, quatre yeux, événements |
| `backend/app/rag/terminology/__init__.py` | 1 | paquet |
| `backend/app/rag/terminology/normalizer.py` | 83 | normalisation de recherche |
| `backend/app/rag/workers/__init__.py` | 1 | paquet |
| `backend/app/rag/workers/tasks.py` | 202 | SHADOW : file `rag` ou thread unique |
| `backend/app/rag/workers/celery_worker.py` | 10 | point d'entrée du worker `rag` |
| `backend/app/application/rag_bridge.py` | 249 | sonde à blanc et pont |
| `backend/migrations/versions/0003_rag.py` | 314 | migration |
| `tools/rag_corpus_run.py` | 262 | lanceur de recette A/B/C |
| `backend/tests/unit/test_rag_lot1_units.py` | 262 | 25 tests |
| `backend/tests/integration/rag_support.py` | 150 | aide de tests (pas de test) |
| `backend/tests/integration/test_rag_lot1_api.py` | 253 | 8 tests |
| `backend/tests/integration/test_rag_lot1_corpus_runner.py` | 147 | 3 tests |
| `backend/tests/integration/test_rag_lot1_disabled.py` | 142 | 4 tests |
| `backend/tests/integration/test_rag_lot1_injection.py` | 211 | 5 tests |
| `backend/tests/integration/test_rag_lot1_migration.py` | 75 | 1 test |
| `backend/tests/integration/test_rag_lot1_shadow.py` | 209 | 5 tests |
| `docs/rag/ARCHITECTURE.md` | — | documentation d'architecture |
| `docs/rag/INSTALLATION-ADMINISTRATION.md` | — | installation et guide d'administration |
| `reports/rag-lot1-20261030/LOT1-RAPPORT.md` | — | ce rapport |
| `reports/rag-lot1-20261030/PHASE0-ETAT-INITIAL.md` | — | état initial vérifié (Phase 0) |
| `reports/rag-lot0-20261030/` (11 fichiers) | — | audit et architecture du LOT 0 : rapport, 4 annexes d'audit, 3 schémas (source Mermaid et rendu PNG) |

## 3. Fichiers existants modifiés (4) et justification

Aucune ligne existante n'est supprimée ni modifiée ; uniquement des ajouts.

| Fichier | Ajout | Justification |
|---|---:|---|
| `backend/app/core/settings.py` | +32 | 6 réglages `rag_*` désactivés par défaut ; refus au démarrage d'une variable `TRANSLATOR_RAG_*` inconnue et d'un budget RAG ≥ budget d'entrée. Indispensable : la configuration est centralisée dans `Settings`. |
| `backend/app/application/jobs.py` | +8 | dans `run_translate`, après la construction existante des options : appel `augment_translation_options` **seulement si** `rag_mode != "DISABLED"`, import paresseux. C'est l'unique point d'accroche sur la traduction. |
| `backend/app/main.py` | +5 | dans `create_app`, montage des routeurs RAG **seulement si** le RAG ou son administration est activé ; sinon rien n'est importé ni monté. |
| `backend/migrations/env.py` | +1 | déclaration des modèles `rag_*` dans les métadonnées Alembic, pour qu'une génération automatique future ne propose pas de supprimer les tables `rag_*`. Sans effet sur les migrations existantes. |

Fichiers gelés **non** modifiés : service de traduction, constructeur de
contexte, moteurs, pipeline documentaire, OCR, rendu, statuts de blocs, règle et
formules de score. Les dépendances (`backend/requirements.txt`, `frontend/`)
sont inchangées ; `compose.yaml` et le chart Helm sont inchangés.

## 4. Migration et retour arrière

Migration `0003_rag` (révision précédente `0002_industrial`) : création de 11
tables `rag_*`, index et contraintes ; aucune table existante modifiée. Le
`downgrade` supprime uniquement ces 11 tables.

| Contrôle | SQLite (test CI) | PostgreSQL 16 (conteneur `postgres:16-bookworm`, local) |
|---|---|---|
| `upgrade 0002 → 0003` | réussi | réussi : 21 tables dont 11 `rag_*` |
| cohérence modèle/schéma (`compare_metadata`) | 0 écart | 0 écart |
| tables existantes après upgrade | identiques | identiques |
| `downgrade → 0002` | 11 tables supprimées, autres identiques | schéma (`pg_dump -s`) identique à 0002, aux jetons aléatoires `\restrict` près |
| ré-upgrade | réussi | réussi, schéma identique au premier upgrade |
| flux HTTP complet | test API | publication quatre yeux, recherche : tenant A 1 résultat, tenant B 0, référentiels vus par B : 0 |

Procédure de retour arrière : voir `docs/rag/INSTALLATION-ADMINISTRATION.md` §9
(tenant, global par `TRANSLATOR_RAG_MODE=DISABLED`, schéma par
`alembic downgrade 0002_industrial` après sauvegarde des tables `rag_*`, code).

## 5. Tests automatisés et résultats réels

### 5.1 Nouveaux tests (51)

| Fichier | Tests | Couverture |
|---|---:|---|
| `test_rag_lot1_units.py` | 25 | réglages et refus des variables inconnues, mode effectif et plafonds moteur, budgets, séquence de réduction, rejet des textes porteurs d'instructions, priorités (glossaire, tenant, domaine, ambiguïté), normalisation, cache isolé |
| `test_rag_lot1_disabled.py` | 4 | sous-processus : aucun module `app.rag` chargé après `create_app` et une traduction ; options identiques ; aucune route ni table `rag_*` ; empreinte de règle identique |
| `test_rag_lot1_migration.py` | 1 | upgrade, cohérence, downgrade limité, ré-upgrade |
| `test_rag_lot1_api.py` | 8 | workflow quatre yeux, rôles, isolation des tenants, bibliothèque commune en lecture seule, journal sans texte |
| `test_rag_lot1_shadow.py` | 5 | traduction et pixels du PDF candidat identiques à DISABLED ; plafond SHADOW pour `offline` ; retour avant la fin de la recherche ; erreurs sans effet (`ERROR_FAIL_SAFE`) ; tâche Celery sur la file `rag` sans texte |
| `test_rag_lot1_injection.py` | 5 | moteur privé **factice explicitement identifié** : seul `document_memory` change, glossaire intact et prioritaire, éviction d'un élément existant → refus, dépassement de budget → réduction puis injection ou abandon, seuls les éléments réellement envoyés sont déclarés, échec de la sonde → aucune injection |
| `test_rag_lot1_corpus_runner.py` | 3 | lanceur A/B/C : sonde ASSISTED, traduction offline A = B = C, refus des sorties dans le dépôt et des appels de modèle non autorisés |

Nature : aucun appel réseau ni modèle réel. La traduction utilise le moteur
`offline` existant ; l'injection est vérifiée avec un moteur de capture qui
reconstruit à blanc les requêtes que le service gelé enverrait.

### 5.2 Exécutions

| Exécution | Commande | Résultat |
|---|---|---|
| lint | `ruff check backend tools` | 0 erreur |
| format | `ruff format --check` sur les fichiers créés | conforme (fichiers existants non reformatés) |
| suite CI complète | `pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security` | **924 réussis, 0 échec, 0 ignoré**, 274,6 s (873 existants + 51 nouveaux) |
| collecte | `pytest backend/tests --collect-only` | 932 (881 + 51) |
| golden (8 originaux locaux, moteur offline) | `pytest backend/tests/golden_dataset` | **8 réussis sur 8**, 20 min ; empreintes du code et des tests identiques au début, à la fin et sur l'arbre committé |
| PostgreSQL 16 | script local (migration + flux HTTP) | réussi (§4) |
| corpus A/B/C (IR des 8 originaux, local) | `tools/rag_corpus_run.py`, moteur offline avec traduction, puis sonde moteur privé sans appel | B identique à A pour 8/8 documents ; 0 bloc modifié sur 1 072 (§9) |

### 5.3 CI GitHub

La CI ne se déclenche que sur `pull_request` ou manuellement. Elle a été
exécutée sur le commit de code du LOT 1 dans les deux dépôts : par la PR
brouillon dans le dépôt privé, et par déclenchement manuel dans le dépôt public
(sans acceptation privée), car l'ouverture de la PR n'y a déclenché aucune
exécution.

| Job ou étape | Dépôt privé | Dépôt public |
|---|---|---|
| `ruff check backend tools` | réussi | réussi |
| pytest, périmètre CI (JUnit) | **924/924**, 0 échec, 0 ignoré (51 RAG) | **924/924**, 0 échec, 0 ignoré (51 RAG) |
| intégration et migrations sur PostgreSQL (JUnit) | **54/54** (26 RAG) | **54/54** (26 RAG) |
| frontend : `npm ci`, typecheck, tests, build | réussis | réussis |
| `pip-audit --strict` | **échec** (Pillow 12.3.0, préexistant) | **échec** (idem) |
| `npm audit --audit-level=high` | **échec** (préexistant) | **échec** (idem) |
| acceptation privée, porte de publication, conteneurs | ignorés (conditions non remplies) | ignorés |

La conclusion globale est donc « échec », uniquement à cause des deux audits de
dépendances, qui échouent déjà sur la base. Le LOT 1 ne modifie aucune
dépendance.

### 5.4 Nombre de tests existants

La consigne cite 874 tests existants. La Phase 0 a mesuré sur la base `d8bb59a`
873 tests dans le périmètre CI et 881 à la collecte complète : les 8 tests
golden sont paramétrés par le catalogue local des 8 originaux (fichier ignoré
par Git) et ne sont collectés que lorsque ce catalogue est présent. Les 873
tests du périmètre CI passent ; les 8 golden sont exécutés séparément (§5.2).

## 6. Sécurité

* **Isolation** : toutes les lectures et écritures passent par le dépôt
  `storage/repository.py`, qui filtre par tenant ; la bibliothèque commune est
  en lecture seule ; le cache est indexé par tenant, mode et version ; testé par
  API et sur PostgreSQL.
* **Validation humaine** : seules les versions publiées d'un référentiel actif
  sont utilisées ; validation par une personne différente de l'auteur et du
  soumetteur (403) ; empreinte du contenu figée à la soumission et vérifiée à la
  validation, à la publication et à la restauration (409) ; chaque action est
  tracée dans `rag_validation_events`.
* **Rôles** : 4 rôles RAG ; attribution réservée à l'administrateur de
  l'application ou à `rag_admin` ; routes d'administration montées seulement si
  `TRANSLATOR_RAG_ADMIN_ENABLED=true` ; authentification, CSRF et révocation de
  session réutilisent la dépendance existante.
* **Injection de consignes** : les textes de référentiel sont nettoyés et ceux
  qui contiennent des motifs d'instruction (balises de rôle, « ignore les
  instructions », etc., en anglais, français, espagnol, allemand et arabe) sont rejetés avant tout envoi ;
  la terminologie ne passe que par le canal de données `document_memory`, jamais
  par les consignes système.
* **Confidentialité** : le journal ne contient jamais de texte de document ni
  de requête : empreinte HMAC-SHA256 (clé dérivée du secret applicatif),
  identifiants, motifs, versions, jetons, latence. Les tâches SHADOW ne
  transportent que des identifiants.
* **Configuration** : variable `TRANSLATOR_RAG_*` inconnue refusée ; budgets
  bornés ; corps de requête stricts (champs inconnus refusés, longueurs
  bornées).
* **Moteurs** : injection uniquement vers le moteur privé ; `interim` et
  `offline` plafonnés à SHADOW.
* **Dépendances** : aucune nouvelle dépendance.

Limites : pas de test d'intrusion ni de revue externe ; la liste des motifs
d'instruction est heuristique (défense en profondeur, pas une garantie).

## 7. Performance

Mesure locale (6 CPU, SQLite, IR synthétique de 40 blocs, aucun modèle) :

| Mesure | n | p50 (ms) | p95 (ms) | max (ms) |
|---|---:|---:|---:|---:|
| point d'intégration, DISABLED | 50 | 0,110 | 0,139 | 0,150 |
| point d'intégration, SHADOW (envoi seul) | 50 | 0,252 | 0,461 | 0,580 |
| point d'intégration, SHADOW avec recherche ralentie de 1 s | 5 | 0,280 | 0,329 | 0,329 |
| point d'intégration, ASSISTED (sonde à blanc, moteur privé) | 50 | 11,073 | 18,414 | 19,671 |
| traduction offline complète, A (DISABLED) | 20 | 2,238 | 4,926 | 7,864 |
| traduction offline complète, B (SHADOW) | 20 | 2,677 | 5,056 | 5,198 |

Avec une recherche ralentie artificiellement de 1 s, le chemin critique reste à
0,28 ms : les 5 recherches se terminent en arrière-plan (5,04 s au total, file à
un thread). Les traductions A et B sont identiques. Le surcoût SHADOW est de
l'ordre de 0,1 à 0,4 ms par traitement, négligeable devant une traduction réelle
(appels de modèle de plusieurs secondes). Le coût de la sonde ASSISTED (≈ 11 ms)
n'est payé que lorsque l'injection est autorisée.

Non mesuré : charge concurrente, PostgreSQL sous charge, gros référentiels
(import en masse et indexation = LOT 2).

## 8. Démonstration fonctionnelle

Démontré par exécution (tests et script PostgreSQL), sans données réelles :

1. Un gestionnaire crée un référentiel métier, une version et des entrées,
   puis la soumet ; il ne peut pas la valider lui-même (403) ; un second
   gestionnaire la valide ; elle est publiée et le référentiel activé.
2. En SHADOW, une traduction produit exactement le même résultat qu'en
   DISABLED ; le journal enregistre la recherche (`SHADOW_ONLY`) avec les
   entrées trouvées et écartées, sans aucun texte.
3. En ASSISTED avec le moteur privé (factice dans les tests), la terminologie
   publiée est ajoutée au seul canal `document_memory` ; le glossaire client
   reste intact et prioritaire ; si le budget ne le permet pas, l'injection est
   réduite ou abandonnée et la requête part comme en DISABLED.
4. Le tenant B ne voit ni les référentiels, ni les résultats, ni le journal du
   tenant A.
5. `GET /api/rag/documents/{id}/explanation` explique ce qui a été trouvé,
   retenu, écarté (avec motif) et réellement injecté.

Non démontré : traduction réelle par le moteur privé avec injection (aucun
modèle privé qualifié disponible) et gain de qualité (corpus annoté = LOT 2).

## 9. Non-régression

| Contrôle | Méthode | Résultat |
|---|---|---|
| Imports en DISABLED | sous-processus : `sys.modules` après `create_app` et une traduction | aucun module `app.rag` |
| Options de traduction | comparaison avec et sans le point d'accroche | identiques |
| OpenAPI | même calcul sur `d8bb59a` et sur le LOT 1 | `053a7024…` identique, 18 chemins, aucun chemin `rag` |
| Tables | inspection de la base créée par l'application | aucune table `rag_*` |
| Empreinte de règle | `tools/recette/ruler_fingerprint.py` | `b0b0261eaabecda8…` identique, mêmes fichiers |
| Fermeture de mesure | chargement de chacun des 31 modules `app.rag` | aucun fichier de la fermeture chargé |
| SHADOW contre DISABLED | traduction e2e, détail normalisé et pixels du PDF candidat | identiques |
| Corpus A/B/C sur les 8 originaux | IR des 8 originaux passées par le point d'intégration de production puis par le service de traduction réel (moteur offline) | B (SHADOW) identique à A (DISABLED) pour 8/8 : options, requêtes, traductions et anomalies ; C plafonné à SHADOW ; 0 bloc modifié sur 1 072 ; 8 recherches SHADOW journalisées sans texte |
| Golden des 8 originaux | arbre LOT 1 contre base (même code de rendu, Pillow 12.3.0) | identique pour 8/8 : 449/449 images PNG identiques, 31/31 pages du PDF candidat identiques au pixel près, 1 338/1 338 blocs OCR inchangés ; les 318 champs JSON qui diffèrent sont tous des chemins de fichiers du répertoire temporaire d'exécution (§9.2) |
| Suite existante | périmètre CI | 873/873 |

### 9.1 Portée des preuves sur les 8 originaux

Le test golden appelle directement `analyze_document` et `translate_document`,
sans passer par `run_translate` où se trouve le point d'accroche : il prouve que
le pipeline documentaire (OCR, segmentation, rendu) est inchangé, pas l'absence
d'effet du point d'accroche. Cette seconde preuve est apportée par les tests
DISABLED et SHADOW de bout en bout (§5.1) et par la recette A/B/C : les IR des 8
originaux y passent par `augment_translation_options` (le même point
d'intégration que `run_translate`) puis par le service de traduction réel.

Recette A/B/C (exécution locale, aucune sortie dans le dépôt, aucun réseau) :
référentiel de termes **synthétiques** publiés par le workflow HTTP quatre yeux
des tests.

| Passe | B contre A | C | Blocs modifiés |
|---|---|---|---:|
| moteur offline, traduction réelle | identique pour 8/8 (options, requêtes, traductions, anomalies) | plafonné à SHADOW (`SHADOW_DISPATCHED`) pour 8/8 | 0 / 1 072 |
| moteur privé, requêtes reconstruites à blanc (aucun appel de modèle) | identique pour 8/8 | `NO_RESULT` pour 8/8 : aucun des termes synthétiques n'apparaît dans ces documents, rien n'est injecté, requêtes identiques à A | 0 / 1 072 |

Cette recette ne mesure pas la qualité : aucun référentiel réel n'existe encore,
et le moteur offline ne fait que des correspondances exactes (975 blocs sur
1 072 restent non traduits par ce moteur, en A comme en B). Le comptage des
jetons y est approximatif (tokenizer privé absent de l'environnement de test).

### 9.2 Comparaison golden : méthode

La référence est le golden exécuté sur la base (même code de rendu, Pillow
12.3.0, même machine, même commande). Les durées, horodatages et empreintes de
fichiers dépendant des chemins sont exclus. Les champs JSON restants qui
diffèrent ont été relus un par un dans les deux exécutions : il s'agit
exclusivement de chemins absolus de fichiers (aperçus de pages et version
candidate), qui deviennent identiques une fois neutralisé le répertoire
temporaire propre à chaque exécution. Aucun texte ni aucune valeur métier ne
diffère.

## 10. Limites et suites

* `ACTIVE` est réservé : ses sources supplémentaires (décisions, contexte pays)
  sont des interfaces vides au LOT 1.
* Correspondance terminologique exacte par n-grammes normalisés : pas de BM25,
  pas de recherche vectorielle, pas d'import en masse (LOT 2/3).
* Aucun référentiel n'est livré ; aucune donnée réelle n'a été injectée.
* Compose et Helm ne déclarent pas de worker `rag` (documenté, optionnel).
* En mode Celery, l'envoi de la tâche SHADOW est synchrone vers le courtier
  (délai de connexion si le courtier tombe pendant un traitement).
* La CI de la base reste rouge sur les audits de dépendances tant que la branche
  de maintenance n'est pas fusionnée.
