# Version finale DICE — contenu et déploiement local

> Branche **`version-finale-DICE`**. Document de référence pour installer la version complète sur un
> poste local (Docker Compose). Le statut de production reste **NO-GO** (§8).
>
> **Niveaux de preuve.** Le code, le chargeur, la recherche par l’API et les tests ont été **exécutés**
> sur cette branche (chemin natif, SQLite et PostgreSQL jetable). La configuration Compose et Helm a été
> **rendue et validée** (`docker compose config`, `helm lint/template`, mêmes commandes que la CI). Les
> images sont **construites par la CI**. Les commandes `docker compose build/up/run` des §3–4 n’ont pas
> été rejouées de bout en bout dans l’environnement de préparation (espace disque insuffisant) : elles
> reprennent la procédure du guide de déploiement (`docs/deploiement.md` §5, exécutée de bout en bout le
> 16/10/2026 sur une version antérieure), complétée pour DICE. Les options propres à ce guide qui n’ont pas été exécutées portent la mention **[non rejoué]**.

## 1. Ce que contient la branche

| Élément | Contenu | Référence |
|---|---|---|
| Application | API FastAPI, worker Celery, frontend Angular, PostgreSQL, Redis, MinIO | `docs/deploiement.md` |
| OCR | Surya OCR 2.5 (Q8_0) **par défaut**, service local isolé, fail-closed, sans repli automatique. Tesseract n’est utilisable que sur choix explicite | `docs/ocr/SURYA.md` |
| **DICE** (RAG terminologique) | Moteur lexical sans base vectorielle (ni Qdrant ni BGE-M3), cycle de validation à quatre yeux, mode **`DISABLED` par défaut** | `docs/rag/` |
| Base de contenu DICE | **47 référentiels**. 46 terminologiques, **22 301 entrées** : EuroVoc 4.24 (23 paires vers le français, 20 537 lignes), 1 654 définitions légales du droit du travail de l’UE alignées vers le français (25 actes, 22 langues ; 1 474 entrées publiées après fusion des termes définis dans plusieurs directives), paire arabe → français (290 lignes, Wikidata CC0). 1 réglementaire : les **textes du droit du travail de l’UE article par article** (25 actes, 571 couples acte-langue, **11 208 articles**, 24 langues ; texte initial du Journal officiel, non consolidé), consultables en lecture seule et jamais injectés dans une traduction | `data/rag-ue/README.md` |
| Langues | Détection et classement des **24 langues officielles de l’UE et de l’arabe**. Les 7 langues historiques gardent exactement la même décision | rapport Phase B §9 |
| Corrections de l’audit | D-DET-02, D-ENG-01, D-OPS-01, F-L2-03, D-OCR-06, D-PERF-TOK | rapport Phase B §2 |
| Sécurité des dépendances | Pillow 13.0.0, Angular 21.2.29, vitest 4.1.12 (maintenance des audits fusionnée) | `reports/maintenance-audits-20261030/` |
| Rapports | Audit (Phase A), corrections et RAG UE (Phase B), note de comité | `reports/` |

Le terme **DICE** désigne le RAG terminologique du produit (`backend/app/rag`). Un tenant ne l’utilise que si l’exploitant l’active (§5).

## 2. Prérequis

- Docker Engine avec Compose v2 et Python 3 (pour générer le fichier `.env`).
- Au moins 8 Gio d’espace disque libre pour les images (`docs/deploiement.md` §5.3), plus 0,9 Go pour les poids Surya.
- Mémoire : les limites configurées totalisent 14,5 Gio (Surya 6 Gio, worker 4 Gio, API 2 Gio, worker DICE 2 Gio, frontend 0,5 Gio). PostgreSQL, Redis et MinIO n’ont pas de limite. Prévoir 16 Gio ou plus. Ces valeurs sont configurées, pas mesurées en charge.
- Un accès Internet pour construire les images et télécharger les poids Surya **une fois**. L’application n’appelle ensuite aucun service externe.

## 3. Installation pas à pas (laboratoire local)

```bash
# 3.1 Code
git clone --branch version-finale-DICE https://github.com/compleoRepos/atelier-documentaire.git
cd atelier-documentaire

# 3.2 Configuration : secrets aléatoires, fichier en mode 600, refus d'écraser un .env existant
python3 tools/create_dev_env.py --out .env
echo "TRANSLATOR_AUTO_CREATE_SCHEMA=false" >> .env              # migrations Alembic explicites
sed -i 's/^TRANSLATOR_RAG_MODE=.*/TRANSLATOR_RAG_MODE=SHADOW/; s/^TRANSLATOR_RAG_ADMIN_ENABLED=.*/TRANSLATOR_RAG_ADMIN_ENABLED=true/' .env
```

`create_dev_env.py` génère toutes les valeurs secrètes, y compris le jeton du service OCR. Ne recopiez jamais un secret d’exemple et ne commitez jamais `.env`.

**3.3 Poids Surya.** Suivez `docs/ocr/SURYA.md` §4 (téléchargement et contrôle SHA-256), puis §7 étape 2 (remplissage du volume `surya-models`). Le conteneur refuse de démarrer si un fichier manque ou si une empreinte diffère (code 78). Sous Compose, le worker dépend de `ocr-surya` : sans poids, il ne démarre pas.

```bash
# 3.4 Validation et construction (le profil rag ajoute l'image du worker DICE)
docker compose --env-file .env config --quiet
docker compose --env-file .env --profile rag build

# 3.5 Services de données
docker compose --env-file .env up -d postgres redis minio minio-provision

# 3.6 Migrations (avant tout démarrage de l'API) — crée aussi les tables DICE
docker compose --env-file .env run --rm --no-deps --entrypoint python api \
  -m alembic -c /app/backend/alembic.ini upgrade head

# 3.7 Deux comptes : l'administrateur et un relecteur (quatre yeux). Mot de passe saisi masqué.
docker compose --env-file .env run --rm --no-deps -it -e TRANSLATOR_BOOTSTRAP_USERNAME=admin \
  --entrypoint python api -m app.core.bootstrap
docker compose --env-file .env run --rm --no-deps -it -e TRANSLATOR_BOOTSTRAP_USERNAME=relecteur \
  -e TRANSLATOR_BOOTSTRAP_ROLE=reviewer --entrypoint python api -m app.core.bootstrap

# 3.8 Démarrage : OCR, application, worker DICE
docker compose --env-file .env up -d ocr-surya          # « healthy » après contrôle des poids (jusqu'à 10 min)
docker compose --env-file .env up -d api worker frontend
docker compose --env-file .env --profile rag up -d rag-worker   # [non rejoué] : rendu Compose validé
docker compose --env-file .env --profile rag ps
```

L’ordre doit être respecté : migration, puis comptes, puis API (`docs/deploiement.md` §5.5–5.6). L’interface est servie sur `http://127.0.0.1:8080` (port `FRONTEND_PORT`). Seul le frontend est publié, et uniquement sur la boucle locale.

## 4. Charger la base DICE (une commande, idempotente)

Les dossiers `tools/` et `data/` ne sont pas dans l’image. On les monte en lecture seule pour la durée de la commande :

```bash
docker compose --env-file .env run --rm --no-deps --entrypoint python \
  -v "$PWD/tools/rag_ue:/app/tools/rag_ue:ro" -v "$PWD/data/rag-ue:/app/data/rag-ue:ro" \
  api /app/tools/rag_ue/charger_dice_ue.py --author admin --validator relecteur
```

**[non rejoué]** dans un conteneur. Le même script a été exécuté en natif sur cette branche avec le même code. Dans l’image, le code est dans `/app/backend`, et le script le trouve à partir de son propre emplacement (`/app/tools/rag_ue`).

Ce que fait le chargeur, dans l’ordre :

1. Il vérifie l’empreinte SHA-256 de **chaque** fichier par rapport aux manifestes (`textes-sha256.json` pour les 25 fichiers de textes, recoupé acte par acte et langue par langue avec `eurlex/manifest.json`). Au moindre écart, il s’arrête avant toute écriture (`MANIFEST_MISMATCH`).
2. Il refuse que l’auteur et le valideur soient la même personne (`FOUR_EYES_REQUIRED`).
3. Il importe chaque fichier en brouillon dans la bibliothèque commune avec l’importeur du produit, soumet la version (auteur), la valide (relecteur), la publie (auteur) puis l’active. Les textes juridiques forment un seul référentiel réglementaire (« EUR-Lex droit du travail UE textes ») qui suit le même cycle ; l’empreinte de leur contenu est figée à la soumission, et toute altération ultérieure bloque la publication (`RAG_CONTENT_CHANGED`). L’option `--sans-textes-juridiques` les exclut.

Un second passage ne modifie rien (0 import, 0 transition). Pour consulter l’état sans rien écrire, remplacez les deux options d’acteur par `--status`.

**Mesuré** (SQLite, chemin natif, base vide) : 47 référentiels importés (46 terminologiques et celui des textes), 141 transitions, 47 activations, **22 301 entrées terminologiques** et **11 208 articles** publiés (571 textes, 25 actes, 24 langues), en 44,4 s. Un second passage ne change rien. L’écart entre les 22 481 lignes terminologiques des fichiers et les 22 301 entrées publiées est attendu : un même terme défini dans plusieurs directives n’est publié qu’une fois (180 doublons signalés `DUPLICATE_IN_FILE`). Le même enchaînement est couvert par `backend/tests/integration/test_dice_charger_ue.py` et, pour les textes, par `backend/tests/integration/test_dice_textes_juridiques.py` (SQLite) et `test_dice_textes_juridiques_postgres.py` (PostgreSQL 16).

## 5. Modes DICE et vérifications

| Mode (`TRANSLATOR_RAG_MODE`) | Effet |
|---|---|
| `DISABLED` (défaut) | Application identique à la version sans DICE. Aucune lecture du RAG |
| `SHADOW` | Recherches en tâche de fond (worker `rag-worker`), journalisées sans texte. La traduction n’est pas modifiée |
| `ASSISTED`, `ACTIVE` | Termes validés injectés dans le prompt du **moteur privé** (`TRANSLATOR_ENGINE=private`). Avec un autre moteur (`offline` par exemple), le mode effectif est plafonné à `SHADOW` |

Le mode appliqué est le plus bas entre le mode global et le **plafond du tenant**. Ce plafond vaut `DISABLED` tant qu’un administrateur ne l’a pas fixé. **Sans cette étape, DICE ne fait rien**, même avec `SHADOW` au niveau global :

```bash
read -rsp "Mot de passe de admin : " PW; echo; export PW
TOKEN=$(curl -fsS -X POST http://127.0.0.1:8080/api/auth/login -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,os; print(json.dumps({"username": "admin", "password": os.environ["PW"]}))')" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'); unset PW
curl -fsS -X POST http://127.0.0.1:8080/api/rag-admin/tenant -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"max_mode": "SHADOW"}'
curl -fsS -X POST http://127.0.0.1:8080/api/rag/search -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"text": "Mindestlohn", "source_language": "de", "target_language": "fr", "domain": "PAYROLL"}'
```

Ces appels sont **[non rejoués]** avec curl. Les mêmes routes et les mêmes corps de requête ont été exécutés par le script de validation de bout en bout et par les tests : connexion, plafond fixé par l’administrateur, modification du plafond refusée au relecteur, recherche. Les procédures de rôles et d’activation progressive sont décrites dans `docs/rag/INSTALLATION-ADMINISTRATION.md` et `docs/rag/RAG-UE.md`.

**Vérifications après installation :**

1. `curl -fsS http://127.0.0.1:8080/api/health` doit renvoyer `"database":true,"storage":true,"queue":true`.
2. Le chargeur, lancé avec `--status`, doit donner 47 référentiels publiés et actifs, dont le référentiel juridique (571 textes, 11 208 articles, 25 actes, 24 langues).
3. Pour la recherche terminologique (dernière commande ci-dessus), précisez `source_language`, `target_language` et **`domain`**. Exemple : `{"text": "Mindestlohn", "source_language": "de", "target_language": "fr", "domain": "PAYROLL"}` renvoie « salaire minimal ». Sans domaine, une entrée spécialisée n’est jamais proposée (`DOMAIN_UNKNOWN`) : c’est une règle de prudence du produit. **Mesuré** : le terme attendu est trouvé dans les 24 langues sources sur 24.
4. Pour les textes du droit du travail, la consultation se fait en lecture seule (mots entiers ; filtres facultatifs de langue et de référence officielle) **[non rejoué]** dans un conteneur :

   ```bash
   docker compose --env-file .env run --rm --no-deps --entrypoint python api \
     -m app.rag.common_library_cli legal-search \
     --query "durée maximale hebdomadaire de travail" --language fr --reference 2003/88
   ```

   **Mesuré** en natif sur la base complète (SQLite, 20 répétitions) : 4 articles trouvés, l’article 6 de la directive 2003/88/CE (« Durée maximale hebdomadaire de travail ») en tête. La recherche dure 50 ms en médiane (95e centile : 54 ms) ; la commande complète, démarrage de Python compris, 0,97 s en médiane. Sur six requêtes types (français, allemand, finnois, toutes langues), la médiane va de 49 à 87 ms. La recherche porte sur des mots entiers : un mot composé (allemand, finnois…) n’est trouvé que sous sa forme complète. Le Journal officiel écrit parfois l’allemand sans tréma (« Hoechstarbeitszeit » dans la directive 2003/88/CE) : la recherche essaie alors aussi l’autre graphie, l’indique dans `spelling_variants` et ne modifie pas le texte officiel. « Höchstarbeitszeit » et « Hoechstarbeitszeit » trouvent toutes deux l’article 6.
5. Pour l’OCR, analysez un scan **synthétique** : les blocs doivent porter la provenance `ocr:surya` (`docs/ocr/SURYA.md` §11).

## 6. Retour arrière

- **DICE** : mettez `TRANSLATOR_RAG_MODE=DISABLED` dans `.env`, puis lancez `docker compose --env-file .env up -d api worker` et `docker compose --env-file .env --profile rag stop rag-worker`. Les référentiels restent en base. Pour retirer une version publiée, utilisez le cycle de vie RAG (`docs/rag/RAG-UE.md`).
- **OCR** : `TRANSLATOR_OCR_BACKEND=tesseract` est réservé à la compatibilité. Sous Compose, il faut alors démarrer le worker avec `up -d --no-deps worker`, sinon Compose démarre aussi `ocr-surya` **[non rejoué]**. Ce n’est jamais un repli automatique.

## 7. Vérification de la version finale

Mesures du 4 novembre 2026, avec les mêmes commandes qu’en Phase A et en Phase B, sur cette branche :

| Contrôle | Résultat mesuré |
|---|---|
| Ruff (périmètre de la CI) | OK |
| Suite backend (unitaires, intégration, bout en bout) | **1 215 réussis, 3 ignorés, 0 échec** (634 s). Les 3 tests ignorés exigent PostgreSQL : ils sont exécutés à part (ligne PostgreSQL). Aucun test disparu ni changé de statut depuis la Phase B (1 207) |
| Golden (8 cas, arbre exporté de la branche) | **8/8** (1 185 s) |
| Tests PostgreSQL 16 (base jetable, supprimée ensuite) | **4/4** : migration, bibliothèque commune, textes du droit du travail |
| Autotest du service Surya | OK |
| `pip-audit` du backend (Pillow 13.0.0) | aucune vulnérabilité connue |
| Compose : `config`, grâce d’arrêt du worker, profil `rag` | OK. `rag-worker` absent par défaut, présent avec `--profile rag` |
| Helm : `lint` et `template` | OK, 11 objets, grâce d’arrêt présente |
| Chargeur DICE sur la base complète | 47 référentiels (46 terminologiques, 1 de textes), 141 transitions, 22 301 entrées terminologiques et 11 208 articles publiés, 44,4 s. Un second passage ne change rien |
| Textes du droit du travail (25 actes, 11 208 articles) | Articles publiés identiques au fichier source, caractère pour caractère ; quatre yeux exigés ; fichier ou manifeste altéré refusé avant toute écriture ; recherche réussie dans les 24 langues, graphies allemandes comprises ; aucune entrée terminologique ni index BM25 créé (tests SQLite et PostgreSQL 16). Recherche : 49 à 87 ms en médiane selon la requête |
| Recherche par l’API | Terme attendu trouvé dans les 24 langues sources ; exemple du §5 vérifié par test |
| Frontend | Identique à la branche de maintenance sécurité (Angular 21.2.29, vitest 4.1.12). Tests Angular et `npm audit` : exécutés par la CI |

Précision de traçabilité : ces contrôles ont été lancés sur le commit précédant ce document, qui contient les textes du droit du travail et le correctif de la recherche allemande. Depuis, seuls des documents ont changé : les empreintes du code produit et des tests sont identiques au début et à la fin de la vérification. Le chargement complet (44,4 s) a été mesuré sur le commit des textes, avant ce correctif, qui ne modifie que la fonction de recherche ; la durée de la recherche a été mesurée avec le correctif. La CI GitHub (« Private document translator ») est lancée manuellement sur cette branche, car elle ne se déclenche que sur une PR ou à la demande. Son résultat figure dans l’onglet Actions.

## 8. Limites et statut (NO-GO production)

- **Licence des poids Surya** : aucune attestation n’a été fournie. Une licence commerciale peut être nécessaire au-delà des seuils de la licence (`docs/ocr/SURYA.md` §2). La production avec Surya est bloquée par conception.
- **Aucune qualification humaine** : aucune ligne de la base DICE n’a été relue par un humain. L’exactitude est estimée par deux évaluateurs automatiques sur échantillon (indice de confiance : plus faible borne basse à 95 % de **93,3 %**, rapport Phase B §10). Ce n’est pas une revue humaine. Les traductions restent soumises à relecture humaine, quel que soit le score.
- **Moteur cible non testé** : le gain de DICE sur la traduction n’est pas mesuré, faute du moteur privé cible.
- **Défauts ouverts** : 12 défauts de l’audit restent ouverts, dont 2 critiques (D-REC-02, D-OPS-02), listés au rapport Phase B §3. IATE n’est pas inclus (compte EU Login requis ; convertisseur fourni).
- **Textes du droit du travail** : texte initial publié au Journal officiel, **non consolidé** (les modifications ultérieures d’un acte n’y figurent pas). Couverture limitée par la source officielle : le règlement 883/2004 n’y est servi que dans 12 langues, l’irlandais n’est servi que pour les 7 actes de 2018 et après, et la Charte des droits fondamentaux n’a pas pu être récupérée. Ces textes sont consultables mais **ne sont pas utilisés par la traduction** (LOT 3 non engagé).
- **Données** : uniquement des sources publiques sous licence ouverte vérifiée, avec mentions dans `data/rag-ue/README.md`. Aucune donnée client.
