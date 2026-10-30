# DICE — Documentary Intelligence & Context Engine (RAG) : architecture du LOT 1

> Statut : **LOT 1 (socle technique)**. Le module est désactivé par défaut
> (`TRANSLATOR_RAG_MODE=DISABLED`). Aucun référentiel n'est livré, aucun import
> en masse, aucune recherche lexicale BM25 ni vectorielle : ces fonctions relèvent
> des LOT 2 et 3. Le LOT 1 fournit le socle (configuration, schéma, versions,
> validation humaine, isolation, journal, modes, point d'intégration, sonde de
> budget, API et lanceur de recette) et prouve qu'il ne change rien quand il est
> désactivé.

## 1. Principe

Le RAG ne remplace ni le moteur de traduction, ni le constructeur de contexte, ni
le glossaire client. Il **prépare** au plus deux canaux déjà prévus par le
constructeur de contexte gelé (`document_memory` et `country_context`) et laisse
le service de traduction gelé construire, budgéter et envoyer les requêtes comme
aujourd'hui.

```
run_translate (jobs.py)
   │  options = {engine, glossary, memory, target_language, ...}   ← inchangé
   │
   ├─ rag_mode == DISABLED ─────────────► options inchangées (aucun import app.rag)
   │
   └─ sinon : rag_bridge.augment_translation_options(...)
          │
          ├─ mode effectif = min(mode global, mode max du tenant, plafond moteur)
          ├─ SHADOW   : planifie une recherche en arrière-plan, rend `options` tel quel
          └─ ASSISTED : plan RAG → canaux → sonde à blanc (requêtes reconstruites
                        sans réseau) → injection seulement si la sonde la prouve
                        sûre ; sinon `options` tel quel
   │
translate_blocks (service gelé) → ContextPackBuilder (gelé) → moteur
```

Le même point d'intégration (`augment_translation_options`) est utilisé par
`run_translate` et par le lanceur de recette `tools/rag_corpus_run.py`.

## 2. Modes

| Mode | Recherche | Injection | Effet sur la traduction |
|---|---|---|---|
| `DISABLED` (défaut) | non | non | aucun ; `app.rag` n'est pas importé, aucune route n'est montée |
| `SHADOW` | oui, en arrière-plan | non | aucun (prouvé : traduction et pixels identiques à DISABLED) |
| `ASSISTED` | oui | terminologie publiée, canal `document_memory` | requêtes enrichies, glossaire client intact et prioritaire |
| `ACTIVE` | oui | terminologie + décisions + contexte pays validé | réservé : les sources de décisions et de contexte pays sont des interfaces LOT 3, vides au LOT 1 |

Le **mode effectif** d'un traitement est le minimum de trois bornes :

1. le mode global (`TRANSLATOR_RAG_MODE`) ;
2. le mode maximal du tenant (`rag_tenant_settings.max_mode`, `DISABLED` si absent) ;
3. le plafond lié au moteur : seule l'injection vers le moteur `private` est
   autorisée ; `offline` (qui ignore le contexte) et `interim` sont plafonnés à
   `SHADOW` avec le motif `ENGINE_IGNORES_CONTEXT` ou `ENGINE_NOT_PRIVATE`.

Un tenant ne peut donc jamais dépasser le mode global.

## 3. Budget de contexte (32K)

Le contrat existant reste la seule autorité : entrée ≤ 22 000 jetons, sortie
≤ 8 000, marge 2 768 (32 768). Le RAG n'ajoute aucun budget hors de ce contrat :

* plafond RAG par requête : 800 jetons en ASSISTED, 1 500 en ACTIVE (paramétrables,
  refusés au démarrage s'ils atteignent le budget d'entrée) ;
* au plus 16 entrées par requête ;
* la **sonde** reconstruit à blanc, avec le service gelé et un moteur de capture
  sans réseau, les requêtes *avec* et *sans* RAG ; elle compare requête par
  requête et n'accepte l'injection que si :
  - le nombre de requêtes et leurs blocs sont identiques ;
  - le glossaire, la mémoire exacte et les autres canaux sont identiques ;
  - aucun élément non RAG n'a été évincé par l'ajustement au budget ;
  - les jetons RAG mesurés restent sous le plafond ;
* sinon, réduction bornée (moitiés successives, au plus 16 essais), puis refus
  (`NOT_INJECTED_*`) : la traduction part alors **exactement** comme en DISABLED.

Seuls les éléments réellement présents dans les requêtes envoyées sont déclarés
injectés (`injected_term_ids`) ; si aucun ne survit au budget, la décision est
`NOT_SENT`.

## 4. Priorités

1. glossaire client (canal `glossary`, jamais modifié) : une entrée RAG dont le
   terme source est couvert par le glossaire est écartée (`GLOSSARY_PRIORITY`) ;
2. pour une même source, le référentiel du tenant écarte la bibliothèque commune
   (`TENANT_PRIORITY`) ;
3. domaine, pays, juridiction déclarés du document : une entrée qui ne correspond
   pas est écartée (`DOMAIN_MISMATCH`, `COUNTRY_MISMATCH`, `JURISDICTION_MISMATCH`) ;
   une entrée spécifique est aussi écartée si le document ne déclare pas la
   dimension (`DOMAIN_UNKNOWN`, `COUNTRY_UNKNOWN`, `JURISDICTION_UNKNOWN`) ;
4. ambiguïté (plusieurs cibles différentes pour une même source après filtres) :
   aucune n'est retenue (`AMBIGUOUS_REQUIRES_CONTEXT`) ;
5. ordre déterministe : sources les plus longues, puis les plus fréquentes, puis
   tenant avant commun, puis forme normalisée et identifiant ; au-delà de la
   limite d'entrées, `ENTRY_LIMIT`.

## 5. Composants (`backend/app/rag/`)

| Paquet | Rôle |
|---|---|
| `config.py` | modes ordonnés, mode effectif, budgets |
| `models.py` | 11 tables `rag_*` (voir §6) |
| `storage/repository.py` | accès aux données, **toujours filtré par tenant** ; bibliothèque commune (tenant NULL) en lecture seule |
| `storage/versioning.py` | référentiels, versions, entrées, machine d'états, quatre yeux, événements |
| `terminology/normalizer.py` | normalisation de recherche (NFKC, casse, apostrophes, tirets, espaces) |
| `core/retrieval.py` | instantanés détachés des versions publiées, cache isolé par tenant/mode/version, correspondance par n-grammes |
| `core/ranking.py` | priorités, refus d'ambiguïté, ordre déterministe |
| `core/context_builder.py` | conversion au format exact des canaux gelés ; rejet des textes porteurs de motifs d'instruction |
| `core/policies.py` | canaux autorisés par mode, séquence de réduction |
| `core/engine.py` | orchestration recherche → classement → plan (sans texte de document dans l'audit) |
| `resolver/document_context.py` | filtres issus du contexte déclaré ; contexte pays seulement s'il est validé |
| `integration/augment_options.py` | point d'intégration unique (DISABLED, SHADOW, ASSISTED, ACTIVE) |
| `workers/tasks.py` | SHADOW : file Celery dédiée `rag` ou exécuteur à un thread, jamais attendu |
| `audit/provenance.py`, `audit/explanation.py` | journal sans texte (empreinte HMAC), explication par document |
| `api/` | routes `/api/rag/*` et `/api/rag-admin/*`, montées seulement si activées |

Hors paquet : `backend/app/application/rag_bridge.py` (sonde à blanc et pont),
`backend/migrations/versions/0003_rag.py`, `tools/rag_corpus_run.py`.

## 6. Données

Tables créées par `0003_rag` (aucune table existante modifiée) :

| Table | Contenu |
|---|---|
| `rag_referentials` | référentiel (type `linguistic`, `business`, `regulatory`), langues, tenant ou commun, actif |
| `rag_referential_versions` | versions numérotées, statut, empreinte du contenu, auteurs |
| `rag_term_entries` | entrées terminologiques (source, cible, langues, domaine, pays, juridiction) |
| `rag_legal_texts`, `rag_legal_passages`, `rag_notion_equivalences` | structures réservées au LOT 3 (vides) |
| `rag_validation_events` | toutes les actions humaines (qui, quand, quoi, empreinte) |
| `rag_document_contexts` | contexte déclaré d'un document (domaine, pays…) et sa validation |
| `rag_tenant_settings` | mode maximal par tenant |
| `rag_role_assignments` | rôles RAG : `rag_admin`, `terminology_manager`, `legal_manager`, `reader` |
| `rag_search_log` | journal des recherches : empreinte HMAC de la requête, filtres, identifiants d'entrées, versions, décision, latence — **jamais de texte** |

Cycle de vie d'une version : `draft → in_review → validated → published →
retired` (et `reject` : `in_review → draft`, `restore` : `retired → published`).
La validation exige une personne différente de l'auteur et de la personne qui a
soumis la version (quatre yeux, refus HTTP 403 `RAG_FOUR_EYES_REQUIRED`). La
soumission fige une empreinte du contenu ; validation, publication et
restauration la recalculent et refusent tout contenu modifié (HTTP 409
`RAG_CONTENT_CHANGED`). Publier une version retire la précédente. Seules
les versions publiées d'un référentiel actif sont utilisées.

## 7. Ce qui est gelé et n'est pas touché

* service de traduction, constructeur de contexte, moteurs, gardes budgétaires ;
* pipeline documentaire, OCR, rendu, statuts de blocs ;
* règle et formules de score (empreinte de règle vérifiée identique) ;
* routes existantes (empreinte OpenAPI identique en DISABLED).

Les seuls fichiers existants modifiés le sont par **ajout** (aucune ligne
supprimée) : voir le rapport du LOT 1.

## 8. Extensions du LOT 2

Détail : [LOT2-TERMINOLOGIE.md](LOT2-TERMINOLOGIE.md). Ajouts sans réécriture
du LOT 1 :

| Paquet | Rôle |
|---|---|
| `terminology/linguistic.py` | normalisation `rag-normalizer-2` (FR, AR, EN, ES, DE), clé pliée, jetons BM25 |
| `terminology/domains.py` | taxonomie de 10 domaines avec parents (proposition à valider par le métier) |
| `terminology/importer.py` | import CSV/XLSX sécurisé, tout ou rien, essai à blanc, doublons |
| `core/lexical.py` | index et recherche BM25 sur PostgreSQL, suggestions **non injectables** |

`core/retrieval.py`, `core/ranking.py`, `core/context_builder.py` et
`core/engine.py` (`dice-engine-2`) gèrent synonymes, variantes et pliage non
ambigu ; `storage/versioning.py` indexe à la publication et à la restauration
et fournit historique et diff ; `workers/tasks.py` porte le correctif F-L2-01.

Tables ajoutées par `0004_rag_lot2` : `rag_lexical_indexes`,
`rag_term_postings`, `rag_import_batches` (les 11 tables du LOT 1 sont
inchangées). En DISABLED, l'empreinte OpenAPI et l'empreinte de règle restent
identiques à la référence de la phase 0 et aucun module `app.rag` n'est importé.
