# DICE (RAG) — LOT 2 : intelligence terminologique et linguistique

Ce document complète [ARCHITECTURE.md](ARCHITECTURE.md) et
[INSTALLATION-ADMINISTRATION.md](INSTALLATION-ADMINISTRATION.md) (LOT 1). Le
LOT 2 n'enlève rien au LOT 1 : DISABLED reste le mode par défaut, les routes
existantes ne changent pas, l'empreinte de règle de score est identique et **la
validation humaine reste obligatoire quel que soit le score**.

Aucune infrastructure nouvelle : ni base vectorielle, ni modèle d'embeddings, ni
extension PostgreSQL. Tout repose sur PostgreSQL/SQLAlchemy déjà en place
(SQLite pour les tests).

## 1. Périmètre

| Sujet | Livré au LOT 2 |
|---|---|
| Langues | FR, AR, EN, ES, DE (toute autre langue est refusée à l'import : `LANGUAGE_UNSUPPORTED`) |
| Normalisation | `rag-normalizer-2` : multilingue, arabe, élisions françaises, pliage contrôlé |
| Correspondance | terme principal, synonymes, variantes régionales, forme pliée **non ambiguë** |
| Domaines | taxonomie de 10 domaines avec parents (proposition **à valider par le métier**) |
| Recherche libre | BM25 sur tables de postings PostgreSQL, **jamais injectée** |
| Import | CSV et XLSX, tout ou rien, essai à blanc par défaut, contrôle des doublons |
| Cycle de vie | historique, diff de versions, restauration (rollback) avec réindexation |
| Correctif LOT 1 | F-L2-01 : la publication SHADOW ne bloque plus le chemin critique |

## 2. Normalisation (`terminology/linguistic.py`)

La normalisation sert **uniquement à la recherche**. Les textes stockés,
affichés ou injectés ne sont jamais modifiés par elle.

* clé de recherche (`search_key`) : normalisation du LOT 1 (NFKC, casse,
  apostrophes, tirets, espaces) + retrait des contrôles bidirectionnels et des
  caractères de largeur nulle, chiffres arabes-indiens et persans convertis en
  ASCII, tatweel et harakat supprimés, alefs hamzés unifiés (`أ إ آ ٱ → ا`),
  élisions françaises séparées (`l' d' qu' j' n' s' c' m' t' lorsqu' puisqu'
  jusqu'`) ;
* clé pliée (`fold_key`) : en plus, diacritiques latins retirés **sauf `ñ`**
  (qui distingue des mots en espagnol), `ß → ss`, `ى → ي`, `ة → ه`, `ؤ → و`,
  `ئ → ي` ;
* alias allemand : `ä → ae`, `ö → oe`, `ü → ue` pour les entrées en allemand
  (translittération courante des saisies et des OCR) ;
* jetons BM25 (`bm25_tokens`) : clé pliée découpée, articles élidés retirés,
  un préfixe arabe léger retiré (le plus long parmi `وال فال بال كال لل ال و ف
  ب ك ل`) lorsque le reste compte au moins trois lettres ; ce n'est pas une
  racinisation complète.

Attention : `search_key` n'est pas idempotente sur une élision (`l'` devient
`l` puis un mot séparé) ; appliquer `fold_key` à une clé déjà calculée, jamais
`search_key` deux fois.

## 3. Correspondance et injection (`core/retrieval.py`, `core/ranking.py`)

L'index en mémoire (cache isolé par tenant/mode/version, LOT 1) indexe désormais
le terme principal, ses synonymes et ses variantes. Chaque correspondance porte
un `match_kind` : `term`, `synonym`, `variant`, et l'indicateur `folded`
lorsqu'elle n'a été trouvée que sur la clé pliée.

* une forme pliée qui correspond à **plusieurs** entrées de cibles différentes
  est refusée (`FOLDED_AMBIGUOUS`) : rien n'est injecté, l'ambiguïté est
  signalée ;
* deux entrées de même source et même domaine avec des cibles différentes
  restent refusées (`AMBIGUOUS_REQUIRES_CONTEXT`, LOT 1) ;
* le glossaire client garde la priorité, y compris sur les clés pliées
  (`GLOSSARY_PRIORITY`) ;
* lorsque la forme lue dans le document diffère du terme du référentiel
  (synonyme, variante, pliage), c'est **la forme lue** qui est transmise comme
  source au constructeur de contexte gelé, pour que son filtre de pertinence
  conserve l'élément ; le texte reste nettoyé des motifs d'instruction ;
* le journal de recherche ne reçoit que des compteurs (`match_kinds`), jamais de
  texte ; l'orchestrateur est versionné `dice-engine-2`.

## 4. Domaines (`terminology/domains.py`) — proposition à valider

| Domaine | Parent |
|---|---|
| `HR` | — |
| `PAYROLL` | `HR` |
| `LEGAL` | — |
| `NOTARIAL` | `LEGAL` |
| `BANKING` | — |
| `FINANCE` | — |
| `TAX` | `FINANCE` |
| `INSURANCE` | `FINANCE` |
| `ADMINISTRATION` | — |
| `ACADEMIC` | — |

Règles : une entrée sans domaine (`GENERAL`) est compatible avec tout
document ; même domaine ou relation parent/enfant (dans les deux sens) =
compatible ; domaines frères (`TAX` et `INSURANCE`) ou sans lien = refus
`DOMAIN_MISMATCH` ; un document sans domaine ou hors taxonomie donne un
résultat « inconnu » signalé `DOMAIN_UNKNOWN` (pas un refus). Une valeur hors
taxonomie est refusée à l'import (`DOMAIN_UNKNOWN`). Des alias multilingues,
insensibles à la casse (`RH`, `paie`, `nómina`, `Lohn`, `banque`…), sont
reconnus.

**Statut** : la liste de domaines visée par la demande initiale n'a pas été
retrouvée dans les documents disponibles ; cette taxonomie est une proposition
technique qui **doit être validée par le métier** avant tout usage réel. Effet
observé sur le corpus synthétique : un contrat de travail classé `HR` qui
contient des clauses juridiques ne reçoit pas les termes `LEGAL` (refus de
domaine, voir le rapport du LOT 2).

## 5. Recherche lexicale BM25 (`core/lexical.py`)

* tables : `rag_term_postings` (un jeton normalisé d'une entrée publiée : terme,
  synonymes, variantes ; `tf`, longueur du document) et `rag_lexical_indexes`
  (état d'index par version : version du normaliseur, empreinte du contenu,
  compteurs, statistiques BM25 précalculées par paire de langues `pair_stats`) ;
* construction **à la publication et à la restauration** d'une version
  (`storage/versioning.transition`), idempotente : une version déjà indexée avec
  le même normaliseur et la même empreinte n'est pas reconstruite ;
* une version publiée mais non indexée (ou indexée avec un autre normaliseur)
  est comptée `unindexed_versions` et ignorée ; `POST
  /api/rag-admin/lexical/rebuild` reconstruit l'index des versions publiées du
  tenant (jamais la bibliothèque commune) ;
* requête : filtres SQL indexés (version publiée visible, tenant ou commun, paire
  de langues), puis score BM25 déterministe (`k1 = 1,2`, `b = 0,75`), ordre
  `(-score, entry_id)`, au plus 50 résultats, au plus 32 jetons de requête ;
* chaque résultat porte `"authority": "suggestion_non_injectable"` et
  `"injectable": false` : **BM25 ne nourrit jamais l'injection**, il sert à la
  recherche libre, aux suggestions et à la détection de doublons.

Mesure (PostgreSQL 16, 20 000 entrées synthétiques, 58 475 postings, 19 Mo,
300 requêtes) : p50 40,9 ms, p95 66,1 ms, maximum 95,3 ms ; publication avec
indexation 9,2 s ; le plan d'exécution utilise l'index.

## 6. Import CSV/XLSX (`terminology/importer.py`)

Route : `POST /api/rag-admin/versions/{version_id}/import?format=auto|csv|xlsx&dry_run=true|false`,
corps brut du fichier (`application/octet-stream`). Rôle : le rôle d'édition du
type de référentiel (comme l'ajout manuel d'entrées). La version doit être un
brouillon.

Colonnes : `source_language`, `source_term`, `target_language`, `target_term`
(obligatoires), `synonyms`, `regional_variants` (listes séparées par `|`),
`definition`, `usage_context`, `register`, `domain`, `country`,
`jurisdiction`, `provenance`. CSV en UTF-8 (BOM toléré), séparateur `;`, `,`
ou tabulation détecté sur la ligne d'en-tête.

* **tout ou rien** : une seule erreur bloque le lot entier ; l'essai à blanc
  (`dry_run=true`, par défaut) produit le même rapport sans rien écrire ;
* limites : `TRANSLATOR_RAG_IMPORT_MAX_BYTES` (5 Mo par défaut),
  `TRANSLATOR_RAG_IMPORT_MAX_ROWS` (5 000), longueur par champ ;
* sécurité XLSX : lecture par `zipfile` + `lxml` sans dépendance nouvelle,
  nombre et taille des membres bornés, ratio de compression borné (anti « zip
  bomb »), DTD et entités refusées (anti XXE), formules refusées
  (`FORMULA_REJECTED`) ; CSV : contenu binaire refusé, cellules commençant par
  `= + @` ou une tabulation refusées (injection de formules) ;
* nettoyage : mêmes motifs d'instruction que le constructeur de contexte
  (`UNSAFE_INSTRUCTION`) ;
* doublons et conflits : `DUPLICATE_IN_FILE`, `ALREADY_IN_DRAFT`,
  `NEAR_DUPLICATE` (même clé pliée), `CONFLICTING_TARGETS`,
  `CHANGES_PUBLISHED_TARGET`, `UNCHANGED_FROM_PUBLISHED`,
  `CONFLICT_WITH_OTHER_REFERENTIAL`, `SYNONYM_COLLISION` ; les avertissements
  n'empêchent pas l'application mais restent dans le rapport soumis aux
  valideurs ;
* trace : `rag_import_batches` conserve l'empreinte SHA-256 du fichier, les
  compteurs et, par numéro de ligne, des **codes seulement** (aucun texte).
  `GET /api/rag-admin/versions/{version_id}/imports` liste les lots.

L'import ne publie rien : la version importée suit le circuit humain du LOT 1
(soumission, validation par une autre personne, publication).

## 7. Historique, diff et retour arrière

* `GET /api/rag-admin/referentials/{referential_id}/history` : versions
  (numéro, statut, nombre d'entrées, auteur de chaque étape, dates de
  publication et de retrait) et événements de validation (action, acteur, rôle,
  commentaire, date) ;
* `GET /api/rag-admin/versions/{version_id}/diff?against=<version>` : ajouts,
  retraits et champs modifiés entre deux versions d'un même référentiel ;
* restauration : `restore` (`retired → published`) recalcule l'empreinte,
  retire la version publiée courante et **réindexe** la version restaurée ;
  l'index lexical suit toujours la version publiée (testé sur SQLite et
  PostgreSQL 16).

## 8. API ajoutée (additive, montée seulement si le RAG est activé)

| Méthode et chemin | Rôle |
|---|---|
| `POST /api/rag-admin/versions/{id}/import` | édition du type de référentiel |
| `GET /api/rag-admin/versions/{id}/imports` | tout rôle RAG |
| `GET /api/rag-admin/referentials/{id}/history` | tout rôle RAG |
| `GET /api/rag-admin/versions/{id}/diff?against=` | tout rôle RAG |
| `GET /api/rag-admin/lexical/status` | tout rôle RAG |
| `POST /api/rag-admin/lexical/rebuild?force=` | `rag_admin` |
| `POST /api/rag/search/lexical` | rôle RAG ou rôle applicatif autorisé au contexte |

Les routes et corps du LOT 1 sont inchangés ; `POST /api/rag/search` renvoie en
plus, de façon additive, `match_kind` et `matched_by`.

## 9. Réglages ajoutés

| Variable | Défaut | Rôle |
|---|---|---|
| `TRANSLATOR_RAG_SHADOW_BROKER_TIMEOUT_SECONDS` | `2.0` | délai de connexion/publication vers le courtier |
| `TRANSLATOR_RAG_SHADOW_BREAKER_SECONDS` | `60` | durée d'ouverture du disjoncteur après un échec |
| `TRANSLATOR_RAG_SHADOW_QUEUE_MAX` | `64` | file bornée de l'éditeur SHADOW |
| `TRANSLATOR_RAG_SHADOW_ON_BROKER_FAILURE` | `drop` | `drop` (observation perdue et comptée) ou `local` (thread local borné) |
| `TRANSLATOR_RAG_IMPORT_MAX_BYTES` | `5000000` | taille maximale d'un import |
| `TRANSLATOR_RAG_IMPORT_MAX_ROWS` | `5000` | lignes maximales d'un import |

## 10. Migration `0004_rag_lot2`

Ajoute trois tables (`rag_lexical_indexes`, `rag_term_postings`,
`rag_import_batches`) ; aucune table existante, ni du LOT 1 ni métier, n'est
modifiée ; `0003_rag` est intacte. `alembic downgrade 0003_rag` supprime
uniquement ces trois tables (vérifié : montée, descente, remontée et
comparaison des métadonnées sur SQLite et PostgreSQL 16). La descente de schéma
**va avec le retour au code du LOT 1** : le code du LOT 2 indexe à la
publication et a besoin de ces tables. Retour arrière sans toucher au schéma :
`TRANSLATOR_RAG_MODE=DISABLED` (ou `max_mode` du tenant), les tables restent
inertes.

## 11. Correctif F-L2-01 (SHADOW en mode Celery)

Constat : en mode Celery, l'envoi vers le courtier était synchrone sur le chemin
critique de la traduction : 6,2 à 6,5 s perdus si le courtier refusait la
connexion ou si le nom ne se résolvait pas, 133,9 s si l'hôte ne répondait pas.
L'affirmation du LOT 1 « un courtier indisponible ne bloque pas le traitement »
était fausse pour la latence.

Correctif (`workers/tasks.py`) : publication par un thread éditeur démon à file
bornée, délai court, disjoncteur, stratégie `drop|local`, compteurs sans texte.
Mesures : chemin critique 0,54 à 0,57 ms ; échec de publication absorbé en 0,2 à
2,2 s dans le thread ; envoi suivant, disjoncteur ouvert, 0,02 à 0,04 ms. Essai
réel sur un Redis local : message limité à cinq identifiants et une
expiration ; journaux sans URL, mot de passe ni identifiant documentaire.

Limite : en stratégie `local`, la recherche SHADOW s'exécute dans le processus
de l'application (thread borné) ; en `drop`, une observation est perdue pendant
l'indisponibilité du courtier (comptée).

## 12. Correctif F-L2-02 (budget de jetons RAG)

Avec `transformers` 5.19 (version épinglée), `apply_chat_template` renvoie un
`BatchEncoding` ; le compteur de messages du constructeur de contexte gelé en
prenait la longueur (2 jetons par requête). Le surcoût RAG valait donc toujours 0
et le garde-fou `BUDGET_EXCEEDED` ne se déclenchait jamais.

Correctif dans `app/application/rag_bridge.py` (hors fermeture d'empreinte) :
`message_tokens` rend le gabarit de conversation puis le compte avec le compteur
du service ; toute erreur de comptage donne `PROBE_FAILED` (refus, la traduction
se poursuit sans RAG). Test : `tests/unit/test_rag_lot2_token_budget.py`
(`BatchEncoding` réel).

Non corrigé (fichier gelé) : côté produit, le rognage du contexte avant envoi
utilise le même compteur et ne rogne donc jamais ; le contrôle préalable 32K,
qui compte correctement, refuse alors la requête (`CONTEXT_OVERFLOW`).

## 13. Constat F-L2-03 (constructeur gelé, non corrigé)

Le filtre de pertinence du constructeur de contexte gelé
(`ContextPackBuilder.relevant_context`) découpe le segment sur les espaces
seulement. Un mot collé à une ponctuation (`Bruttogehalt:`) ne correspond pas à
l'entrée, qui est retirée du contexte quand aucun autre mot du segment ne la
retrouve. Effets mesurés : une entrée du **glossaire client** jamais envoyée au
moteur (avec ou sans RAG) et 12,0 % des propositions du RAG écartées sur le
corpus synthétique. Le correctif (découpage sans ponctuation) modifie la
fermeture d'empreinte historique : branche séparée, rejeu golden et validation
explicite. Caractérisation : `tests/unit/test_rag_lot2_frozen_findings.py`
(`xfail` strict, échouera dès la correction).

## 14. Limites connues

* la taxonomie de domaines n'est pas validée par le métier ; le refus de domaine
  peut priver un document mixte (contrat de travail avec clauses juridiques) de
  termes utiles ;
* BM25 est lexical : aucune proximité sémantique, pas de racinisation
  complète (seuls les clitiques arabes légers sont retirés) ;
* le pipeline de traduction ne traduit que **vers le français** (les blocs dont
  la langue source est le français ne sont jamais envoyés au moteur,
  comportement historique conservé) : les référentiels FR→EN sont importables et
  recherchables, mais jamais injectés, puisqu'aucune requête n'est envoyée ; la
  traduction FR→EN n'est pas exercée de bout en bout ;
* les mesures de qualité du LOT 2 portent sur un corpus **synthétique** ; la
  fidélité sémantique n'est pas mesurée sans annotateurs humains (voir
  [ANNOTATION-HUMAINE.md](ANNOTATION-HUMAINE.md)).
