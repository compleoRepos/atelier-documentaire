# DICE (RAG) — installation, activation et administration (LOT 1)

> Par défaut, rien n'est à faire : `TRANSLATOR_RAG_MODE=DISABLED` laisse
> l'application **strictement identique** (aucun import du module, aucune route,
> aucune table créée par l'application). Ce guide décrit l'activation
> progressive, réversible à tout moment.

## 1. Prérequis

* Aucune nouvelle dépendance Python ou npm (fichiers de dépendances inchangés).
* Base : PostgreSQL 16 (vérifié) ou SQLite (tests). La migration Alembic
  `0003_rag` ajoute 11 tables `rag_*` et ne modifie aucune table existante.
* Mode Celery : le courtier existant suffit ; un worker dédié à la file `rag`
  est recommandé en SHADOW (§4).

## 2. Variables d'environnement

Toutes les variables `TRANSLATOR_RAG_*` sont validées au démarrage. Une variable
inconnue (faute de frappe, variable d'un lot futur) **fait échouer le démarrage**
au lieu d'être ignorée.

| Variable | Défaut | Bornes | Rôle |
|---|---|---|---|
| `TRANSLATOR_RAG_MODE` | `DISABLED` | `DISABLED`, `SHADOW`, `ASSISTED`, `ACTIVE` | mode global (plafond de tous les tenants) |
| `TRANSLATOR_RAG_ADMIN_ENABLED` | `false` | booléen | monte `/api/rag-admin/*` (référentiels, rôles, mode tenant) |
| `TRANSLATOR_RAG_ASSISTED_MAX_TOKENS` | `800` | 1–4000, < budget d'entrée | plafond RAG par requête en ASSISTED |
| `TRANSLATOR_RAG_ACTIVE_MAX_TOKENS` | `1500` | 1–4000, < budget d'entrée | plafond RAG par requête en ACTIVE |
| `TRANSLATOR_RAG_MAX_ENTRIES` | `16` | 1–16 | entrées terminologiques maximales par requête |
| `TRANSLATOR_RAG_SHADOW_TASK_EXPIRES_SECONDS` | `3600` | 60–86400 | expiration d'une recherche SHADOW non consommée (Celery) |

Les routes `/api/rag/*` (statut, contexte documentaire, explication, recherche)
sont montées dès que le mode n'est pas `DISABLED` ou que l'administration est
activée.

## 3. Migration

```bash
cd backend
alembic upgrade head          # 0002_industrial -> 0003_rag
alembic current               # doit afficher 0003_rag
```

En mode `TRANSLATOR_AUTO_CREATE_SCHEMA=true` (développement), seules les tables
`rag_*` sont créées, et seulement si le module est activé.

## 4. Worker SHADOW (mode Celery)

En `TRANSLATOR_EXECUTION_MODE=celery`, chaque traduction en SHADOW publie une
tâche **sans texte** (identifiants seulement) sur la file distincte `rag` ; la
traduction ne l'attend jamais. Démarrer un worker dédié, séparé de la file
`documents` :

```bash
celery -A app.rag.workers.celery_worker:app worker -Q rag --concurrency 1 --loglevel=INFO
```

Exemple de service Compose additionnel (non livré dans `compose.yaml` au LOT 1,
pour que le déploiement par défaut reste identique) : reprendre le service
`worker` existant en remplaçant la commande par la ligne ci-dessus.

Sans worker `rag`, les tâches SHADOW expirent (variable ci-dessus) sans effet sur
la traduction. En mode `inline`, la recherche SHADOW s'exécute dans un exécuteur
à un seul thread du processus, sans attente.

Limite connue : en mode Celery, la publication de la tâche est un envoi
synchrone vers le courtier ; si le courtier devient indisponible pendant un
traitement, l'envoi échoue après le délai de connexion du client Celery ;
l'erreur est capturée (décision `ERROR_FAIL_SAFE`) et la traduction se poursuit
avec les options inchangées, comme en DISABLED.

## 5. Activation progressive recommandée

1. **Migration** puis `TRANSLATOR_RAG_ADMIN_ENABLED=true`, mode toujours
   `DISABLED` : constituer et valider les référentiels sans aucun effet sur les
   traductions.
2. `TRANSLATOR_RAG_MODE=SHADOW` et, pour chaque tenant pilote,
   `max_mode=SHADOW` : le système cherche, journalise, n'injecte rien. Contrôler
   le journal (§8).
3. `TRANSLATOR_RAG_MODE=ASSISTED` et `max_mode=ASSISTED` pour les tenants
   validés : injection de la terminologie publiée, uniquement vers le moteur
   privé et uniquement si la sonde de budget la prouve sûre.
4. `ACTIVE` : réservé ; ses sources supplémentaires (décisions, contexte pays)
   sont livrées aux lots suivants.

Le mode effectif reste le minimum du mode global, du mode du tenant et du
plafond moteur (`offline` et `interim` : SHADOW au plus).

## 6. Rôles

| Rôle | Droits |
|---|---|
| administrateur de l'application (`admin`) ou `rag_admin` | attribuer les rôles RAG, fixer le mode maximal du tenant |
| `rag_admin` | activer/désactiver un référentiel ; gérer la terminologie |
| `terminology_manager` | créer référentiels et versions linguistiques/métier, ajouter des entrées, soumettre, valider (si autre personne), publier, retirer |
| `legal_manager` | mêmes actions, pour les référentiels réglementaires (LOT 3) |
| `reader` | consulter référentiels, entrées, événements, journal |
| `reviewer` / `admin` de l'application | déclarer et valider le contexte d'un document ; rechercher (aussi permis à tout rôle RAG) |

Tous les accès sont limités au tenant de l'utilisateur. La bibliothèque commune
(référentiels sans tenant) est en lecture seule par l'API.

## 7. Workflow d'un référentiel (API)

Préfixe `/api/rag-admin` (session et jeton CSRF existants) :

```text
POST /referentials                         {kind, name, domain?, country?, jurisdiction?, languages}
POST /referentials/{id}/versions           {copy_from?}
POST /versions/{id}/entries                {entries: [{source_language, source_term, target_language, target_term, ...}]}
POST /versions/{id}/transitions            {action: "submit"}     # auteur A
POST /versions/{id}/transitions            {action: "validate"}   # personne B ≠ A (sinon 403)
POST /versions/{id}/transitions            {action: "publish"}
POST /referentials/{id}/active             {active: true}         # rag_admin
GET  /versions/{id}/events                 # traçabilité complète
```

Rôles et tenant :

```text
POST /roles    {user_id, role, grant: true|false}
POST /tenant   {max_mode: "DISABLED"|"SHADOW"|"ASSISTED"|"ACTIVE"}
```

Contexte d'un document (préfixe `/api/rag`) :

```text
POST /documents/{doc_id}/context           {source_language?, target_language?, source_country?, target_country?,
                                            jurisdiction?, document_date?, legal_reference_date?}
POST /documents/{doc_id}/context/validate  # autre personne que le déclarant
GET  /documents/{doc_id}/explanation       # ce que le RAG a trouvé, retenu, écarté, injecté
POST /search                               {text, source_language, target_language?, domain?, limit?}
```

## 8. Supervision

`GET /api/rag-admin/search-log` : pour chaque recherche, mode, origine,
empreinte HMAC de la requête (jamais le texte), filtres, identifiants des
entrées retenues et écartées avec motif, versions utilisées, décision
(`SHADOW_ONLY`, `INJECTED`, `NOT_SENT`, `ABANDONED`, `ERROR_FAIL_SAFE`…),
jetons et latence.

Indicateurs à suivre en SHADOW avant tout passage en ASSISTED : taux de
recherches avec résultat, motifs d'exclusion dominants (`DOMAIN_UNKNOWN`,
`AMBIGUOUS_REQUIRES_CONTEXT`…), latence, erreurs `ERROR_FAIL_SAFE`.

La relecture humaine des traductions reste obligatoire quel que soit le mode.

## 9. Retour arrière

| Niveau | Action | Effet |
|---|---|---|
| tenant | `POST /api/rag-admin/tenant {"max_mode": "DISABLED"}` | immédiat pour ce tenant |
| global | `TRANSLATOR_RAG_MODE=DISABLED`, `TRANSLATOR_RAG_ADMIN_ENABLED=false`, redémarrage | application identique à avant le LOT 1 ; les tables `rag_*` restent inertes |
| schéma | sauvegarde `pg_dump -t 'rag_*'`, puis `alembic downgrade 0002_industrial` | supprime uniquement les 11 tables `rag_*` (vérifié sur PostgreSQL 16 : schéma identique à 0002) |
| code | annulation du commit de fusion du LOT 1 | à faire après le retour arrière global |

## 10. Recette sans modèle

`tools/rag_corpus_run.py` exécute sur les mêmes IR les variantes A (DISABLED),
B (SHADOW) et C (ASSISTED) à travers le point d'intégration de production, avec
des bases et un stockage temporaires, une sortie hors dépôt et un résumé sans
texte. Il échoue (code 2) si B diffère de A. Les appels de modèle réels exigent
`--allow-model-calls`.
