# DICE (RAG) — rapport du LOT 2 : intelligence terminologique et linguistique

> Branche `feature/rag-lot2-terminologie-20261030`, empilée sur
> `feature/rag-lot1-socle-20261030`. Date : 2026-10-30. Toutes les valeurs
> proviennent d'exécutions réelles sur l'arbre final du LOT 2, sauf mention
> contraire. Documentation technique : [LOT2-TERMINOLOGIE.md](../../docs/rag/LOT2-TERMINOLOGIE.md).

> **Verdict du LOT 2 : GO technique conditionnel pour une recette métier
> (SHADOW, puis ASSISTED sur le moteur privé) ; NO-GO pour la production.**
> Le verdict RUN29 (NO-GO bancaire, 8/8 `REVIEW_REQUIRED`) est inchangé.
> **Un humain valide chaque document, quel que soit le score** : aucun
> résultat de ce rapport ne réduit la revue humaine.
>
> Ce qui est acquis (mesuré) : socle terminologique complet et testé (996 tests
> backend réussis, 0 échec ; PostgreSQL 16 réel), mode DISABLED strictement
> inchangé, isolation tenant, circuit quatre yeux, retour arrière. Sur le corpus
> **synthétique**, la conformité au référentiel passe de 62,3 % (A, sans RAG) à
> 93,4 % (C) sans perte sur les nombres (188/188) ni injection ambiguë (0).
>
> Ce qui empêche un GO production : fidélité sémantique **non mesurée** (aucun
> annotateur humain) ; taxonomie de domaines **non validée** ; défaut produit
> F-L2-03 (glossaire client écarté par la ponctuation, fichier gelé, non
> corrigé) ; traduction depuis le français non prise en charge par le pipeline ;
> moteur gpt-oss-20b non qualifié et non déterministe d'une passe à l'autre.
> Le LOT 3 n'est pas commencé.

## 1. Erratum du LOT 1 (défaut F-L2-01)

Le rapport du LOT 1 affirmait : « SHADOW ne ralentit pas le chemin critique —
atteint ». C'était **faux en mode Celery**. La vérification demandée avant le
LOT 2 a montré que l'envoi vers le courtier était synchrone sur le chemin
critique de la traduction :

| Situation du courtier (mode Celery) | Temps perdu sur le chemin critique avant correctif |
|---|---|
| connexion refusée | 6,2 à 6,5 s |
| nom introuvable (DNS) | 6,2 à 6,5 s |
| hôte silencieux | 133,9 s |

L'erreur était bien rattrapée (la traduction se poursuivait sans RAG), mais
avec ce retard. Le mode `inline` (thread local) mesuré au LOT 1 n'était pas
concerné.

Correctif (`backend/app/rag/workers/tasks.py`, réglages
`TRANSLATOR_RAG_SHADOW_*`) : publication par un thread éditeur à file bornée,
délai court, disjoncteur, stratégie `drop` (défaut : observation perdue et
comptée) ou `local` (recherche dans un thread local borné), compteurs sans
texte.

| Mesure après correctif | Valeur |
|---|---|
| coût sur le chemin critique, courtier indisponible | 0,544 à 0,566 ms |
| échec de publication absorbé dans le thread éditeur | 0,211 à 2,225 s (hors chemin critique) |
| envoi suivant, disjoncteur ouvert | 0,02 à 0,04 ms |
| courtier Redis local réel | publication réussie ; message limité à 5 identifiants + expiration |
| journaux avec secrets simulés | ni URL, ni mot de passe, ni identifiant documentaire |

Six tests dédiés (`test_rag_lot2_broker.py`). Le test du LOT 1
`test_celery_dispatch_uses_rag_queue_and_carries_no_text` a été adapté (deux
lignes ajoutées : remise à zéro du disjoncteur, attente du thread éditeur) car
la publication est désormais asynchrone.

## 2. Ce qui a été livré

| Exigence | Réalisation | Preuve |
|---|---|---|
| Référentiels FR/AR/EN/ES/DE | langues contrôlées à l'import et en recherche | tests linguistiques et d'import |
| Domaines | taxonomie de 10 domaines avec parents — **proposition non validée par le métier** | `domains.py`, tests |
| Normalisation linguistique et arabe | `rag-normalizer-2` (harakat, tatweel, alefs, chiffres, bidi, élisions, pliage contrôlé) | 26 tests unitaires |
| Synonymes et variantes | indexés et injectables ; la forme lue est transmise au constructeur gelé | tests unitaires et d'intégration |
| Recherche exacte | conservée (LOT 1) + forme pliée **non ambiguë** | tests |
| BM25 PostgreSQL | tables de postings, sans extension, suggestions **jamais injectées** | tests SQLite + PostgreSQL 16, mesure 20 000 entrées |
| Import CSV/XLSX | tout ou rien, essai à blanc, sécurité zip/XML/formules, doublons | 4 tests d'intégration, corpus importé réellement |
| Ambiguïtés | refus `AMBIGUOUS_REQUIRES_CONTEXT` et `FOLDED_AMBIGUOUS`, signalées | tests + corpus |
| Versionnement, publication, historique, retour arrière | historique, diff, restauration avec réindexation | tests SQLite + PostgreSQL 16 |
| Validation humaine | circuit quatre yeux du LOT 1 inchangé, import sans publication | tests |
| Corpus synthétique, A/B/C, moteur réel | 40 documents, 8 catégories, 5 paires ; gpt-oss-20b local | §7 et §8 |

Aucune base vectorielle, aucun modèle d'embeddings, aucune extension PostgreSQL,
aucune dépendance nouvelle (0 ligne modifiée dans `requirements`, `pyproject`,
`package.json`, fichiers de verrouillage).

## 3. Fichiers créés (22)

| Fichier | Rôle |
|---|---|
| `backend/app/rag/terminology/linguistic.py` | normalisation, pliage, jetons BM25 |
| `backend/app/rag/terminology/domains.py` | taxonomie et compatibilité de domaines |
| `backend/app/rag/terminology/importer.py` | import CSV/XLSX sécurisé |
| `backend/app/rag/core/lexical.py` | index et recherche BM25 |
| `backend/migrations/versions/0004_rag_lot2.py` | trois tables `rag_*` |
| `backend/tests/unit/test_rag_lot2_linguistic.py` | 26 tests |
| `backend/tests/unit/test_rag_lot2_tools.py` | 24 tests (outils de recette) |
| `backend/tests/unit/test_rag_lot2_token_budget.py` | 5 tests (F-L2-02, budget de jetons) |
| `backend/tests/unit/test_rag_lot2_frozen_findings.py` | 2 tests (caractérisation F-L2-03, dont 1 `xfail` strict) |
| `backend/tests/integration/test_rag_lot2_terminology.py` | 5 tests (recherche, BM25, publication, retour arrière, diff, historique, isolation) |
| `backend/tests/integration/test_rag_lot2_import.py` | 4 tests (validations, doublons, sécurité, rôles, traces sans texte) |
| `backend/tests/integration/test_rag_lot2_broker.py` | 6 tests (F-L2-01) |
| `backend/tests/integration/test_rag_lot2_migration.py` | 2 tests (SQLite, PostgreSQL) |
| `backend/tests/integration/test_rag_lot2_postgres.py` | 1 test BM25 de bout en bout sur PostgreSQL |
| `docs/rag/LOT2-TERMINOLOGIE.md` | documentation technique |
| `docs/rag/ANNOTATION-HUMAINE.md` | protocole d'annotation |
| `tools/rag_lot2_corpus.py` | générateur de corpus synthétique |
| `tools/rag_lot2_eval.py` | évaluation objective et paquet d'annotation aveugle |
| `reports/rag-lot2-20261030/LOT2-RAPPORT.md` | ce rapport |
| `reports/rag-lot2-20261030/RESULTATS-ABC.json` | agrégats A/B/C sans texte |
| `reports/rag-lot2-20261030/RESULTATS-PAR-DOCUMENT.json` | compteurs par document, sans texte |
| `reports/rag-lot2-20261030/CORPUS-SYNTHETIQUE.md` | composition du corpus et limites |

## 4. Fichiers existants modifiés (18) et justification

| Fichier | +/− | Justification |
|---|---|---|
| `backend/app/rag/core/retrieval.py` | +109/−23 | synonymes, variantes, clé pliée, `MatchResult` ; `match()` du LOT 1 conservé |
| `backend/app/rag/core/ranking.py` | +53/−12 | priorité glossaire sur clés pliées, domaines v2, `FOLDED_AMBIGUOUS` |
| `backend/app/rag/core/context_builder.py` | +13/−1 | source = forme lue (synonyme, variante, pliage) |
| `backend/app/rag/core/engine.py` | +20/−5 | `dice-engine-2`, compteurs `match_kinds`, champs additifs |
| `backend/app/rag/workers/tasks.py` | +169/−30 | correctif F-L2-01 |
| `backend/app/rag/models.py` | +91/−1 | trois modèles LOT 2 dans une liste séparée (les 11 tables du LOT 1 intactes) |
| `backend/app/rag/storage/versioning.py` | +131/−0 | indexation à la publication et à la restauration, diff, historique |
| `backend/app/rag/api/admin_routes.py` | +133/−2 | routes d'import, traces, historique, diff, index lexical |
| `backend/app/rag/api/routes.py` | +48/−1 | `POST /api/rag/search/lexical` |
| `backend/app/rag/schemas.py` | +10/−0 | schéma de recherche lexicale |
| `backend/app/core/settings.py` | +11/−0 | réglages SHADOW et import (ajout seul) |
| `backend/app/application/rag_bridge.py` | +24/−3 | correctif F-L2-02 (comptage réel des jetons, refus si le comptage échoue) |
| `backend/tests/integration/test_rag_lot1_migration.py` | +17/−3 | vise explicitement `0003_rag` et ignore seulement les tables du LOT 2 |
| `backend/tests/integration/test_rag_lot1_shadow.py` | +2/−0 | publication asynchrone (F-L2-01) |
| `tools/rag_corpus_run.py` | +58/−3 | compteurs d'usage, comptage F-L2-02, `--dump-translations` hors dépôt |
| `.github/workflows/ci.yml` | +12/−0 | étape PostgreSQL dédiée (migration 0004 et BM25) |
| `docs/rag/ARCHITECTURE.md` | +22/−0 | §8 extensions LOT 2 |
| `docs/rag/INSTALLATION-ADMINISTRATION.md` | +25/−0 | §11–12 migration, réglages, retour arrière, recette |

Hors du paquet `app.rag`, seuls sont modifiés : les ajouts à `settings.py`, la
CI et le pont RAG `rag_bridge.py` (créé au LOT 1, chargé seulement hors
DISABLED, hors fermeture d'empreinte). Aucun fichier du service de traduction,
du pipeline documentaire, des moteurs, du score ou de la fermeture de mesure
n'est touché (34 fichiers identiques, §10).

## 5. Migration et retour arrière

`0004_rag_lot2` ajoute `rag_lexical_indexes`, `rag_term_postings`,
`rag_import_batches`. `0003_rag` n'est pas modifiée. Vérifié sur SQLite et
PostgreSQL 16 : montée, cohérence modèle/schéma (`compare_metadata` vide),
descente vers `0003_rag` (seules les trois tables disparaissent, schéma du
LOT 1 identique), remontée. La descente de schéma va avec le retour au code du
LOT 1 ; sans toucher au schéma, `TRANSLATOR_RAG_MODE=DISABLED` suffit.

## 6. Tests automatisés et résultats réels

| Contrôle | Résultat |
|---|---|
| `ruff check backend tools` | aucune remarque |
| suite backend complète, commande de la CI (unit, integration, e2e, regression, security) | **996 réussis**, 2 ignorés (PostgreSQL, ligne suivante), 1 échec attendu (`xfail` F-L2-03), **0 échec** ; 4 min 57 s |
| tests sur PostgreSQL 16 réel, base vierge (migration 0004, BM25 de bout en bout) | 3 réussis, 0 ignoré |
| tests RAG LOT 1 + LOT 2 | 123 réussis, 2 ignorés (PostgreSQL), 1 `xfail` |
| dont tests propres au LOT 2 | 75 : 26 linguistique, 24 outils, 5 budget de jetons, 2 constat F-L2-03, 6 courtier, 5 terminologie, 4 import, 2 migration, 1 PostgreSQL |

Le test `xfail(strict=True)` documente le défaut F-L2-03 du constructeur gelé :
il échouera dès que le défaut sera corrigé, ce qui obligera à mettre à jour
l'attente.

## 7. Corpus synthétique

Composition et règles détaillées : [CORPUS-SYNTHETIQUE.md](CORPUS-SYNTHETIQUE.md).
40 documents = 8 catégories (attestation de travail, contrat de travail,
bulletin de paie, relevé bancaire, courrier administratif, procuration
juridique, tableau récapitulatif, document « scanné » avec bruit d'OCR simulé)
× 5 paires (EN→FR, AR→FR, ES→FR, DE→FR, FR→EN). Personnes, sociétés,
identifiants et montants sont fictifs (`Nour TEST`, `ALPHA DEMO SARL`,
`XX00 TEST …`). Référentiel de 169 lignes importé par la route d'import réelle
(essai à blanc puis application : 0 erreur, 2 avertissements
`CONFLICTING_TARGETS` qui sont les deux ambiguïtés voulues), puis soumis,
validé par une deuxième personne et publié.

Pièges construits : synonymes et variantes en source, bruit d'OCR (accents
perdus, translittération allemande, harakat et tatweel arabes, chiffres
arabes-indiens, espaces), terme ambigu (`deposit` → `dépôt`/`caution`), terme
d'un domaine frère (`INSURANCE` dans un bulletin de paie), glossaire client en
conflit avec le référentiel.

**Références** : les « références candidates » sont rédigées par
construction par l'outil, **pas par des humains**. Elles servent seulement au
chrF, indicateur de substitution.

## 8. A/B/C sur le moteur privé réel

### 8.1 Protocole

* Moteur : gpt-oss-20b local (GGUF MXFP4, llama.cpp), accessible en local
  uniquement, contexte 32 768, raisonnement « low », température 0 (fixée par le
  service), une seule file, CPU 6 cœurs. **Moteur non qualifié** : il ne remplace
  pas la validation humaine.
* A = sans RAG ; B = SHADOW (observe, n'injecte rien) sur 8 documents (un par
  catégorie) ; C = ASSISTED (injection des seuls termes exacts, synonymes,
  variantes ou pliés **non ambigus** ; résultats BM25 jamais injectés).
* 32 documents X→FR traduits en A et en C, 8 en B : **72 traductions réelles**,
  4 342 s (1 h 12). FR→EN : plan RAG seulement (§8.6).
* Évaluation automatique par construction (`tools/rag_lot2_eval.py`) :
  conformité des termes au référentiel publié, glossaire client, nombres, dates
  et identifiants, cohérence des répétitions, ambiguïtés et domaine frère, chrF
  contre références candidates **non humaines**. Les 40 sources et le
  référentiel ont été vérifiés identiques octet pour octet avant évaluation.
* Les documents non traduits ne comptent ni comme succès ni comme échec dans les
  mesures de sortie ; ils comptent dans les mesures du plan RAG (test dédié).

### 8.2 Résultats globaux (32 documents traduits)

| Indicateur | A (sans RAG) | C (ASSISTED) |
|---|---|---|
| termes conformes au référentiel (stricts) | 62,3 % (132/212) | **93,4 % (198/212)** |
| termes attendus effectivement injectés (rappel de sélection) | — | 88,7 % (188/212) |
| termes injectés repris par le modèle (conformité) | — | 94,7 % |
| termes ambigus injectés / termes d'un domaine frère injectés | 0 / 0 | **0 / 0** |
| glossaire client respecté | 7/8 | 7/8 (seul échec : F-L2-03) |
| glossaire client remplacé par le référentiel | 0 | **0** |
| montants, dates, identifiants, nombres conservés | 188/188 | 188/188 |
| nombres ajoutés par le modèle | 0 | 0 |
| termes répétés traduits de façon cohérente | 3/12 | **12/12** |
| anomalies du service / blocs non traduits | 2 / 2 | 2 / 2 (les mêmes, documents « scannés » AR et EN : `PROTECTED_ENTITY_CHANGED`) |
| chrF, indicateur de substitution | 75,33 | 80,30 |
| jetons d'entrée / de sortie (usage moteur) | 16 903 / 9 335 | 19 459 (+15,1 %) / 9 620 (+3,1 %) |

**Lecture prudente.** « Conforme au référentiel » mesure l'alignement sur la
terminologie publiée par le client, pas la qualité de la traduction : une
traduction A différente du référentiel peut être juste. Le gain de C est en
partie attendu par construction (C reçoit la cible). Le chrF est biaisé en
faveur de C (références candidates rédigées avec les termes du référentiel). Une
seule passe par variante, 32 documents : aucune significativité statistique
n'est revendiquée.

### 8.3 Par paire de langues

| Paire | Termes stricts A → C | Rappel de sélection C | Conformité du modèle C | Glossaire A / C | chrF A → C |
|---|---|---|---|---|---|
| AR→FR | 64,2 % → 98,1 % | 90,6 % | 97,9 % | 2/2 / 2/2 | 75,27 → 80,80 |
| DE→FR | 66,0 % → 90,6 % | 79,2 % | 95,2 % | 1/2 / 1/2 | 73,04 → 75,48 |
| EN→FR | 58,5 % → 88,7 % | 92,5 % | 89,8 % | 2/2 / 2/2 | 73,99 → 79,78 |
| ES→FR | 60,4 % → 96,2 % | 92,5 % | 95,9 % | 2/2 / 2/2 | 79,01 → 85,14 |
| FR→EN | non mesurable (§8.6) | — | — | — | — |

L'allemand a le rappel le plus faible : dans ce corpus, ses libellés sont
souvent un seul mot composé suivi de deux-points (`Familienstand:`), cas exact
du défaut F-L2-03.

### 8.4 Par domaine et par catégorie

| Domaine du document | Documents | Termes stricts A → C | Cohérence des répétitions A → C |
|---|---|---|---|
| HR | 12 | 60,6 % → 93,3 % | 0/4 → 4/4 |
| PAYROLL | 8 | 70,0 % → 95,0 % | — |
| BANKING | 4 | 66,7 % → 91,7 % | — |
| ADMINISTRATION | 4 | 25,0 % → 90,0 % | 0/4 → 4/4 |
| LEGAL | 4 | 83,3 % → 95,8 % | 3/4 → 4/4 |

Les domaines FINANCE, TAX, INSURANCE (hors piège de domaine frère), NOTARIAL et
ACADEMIC ne sont pas couverts par un document du corpus.

| Catégorie | Termes stricts A → C | Conformité du modèle C | chrF A → C |
|---|---|---|---|
| attestation de travail | 75,0 % → 96,4 % | 96,2 % | 70,91 → 72,27 |
| contrat de travail | 54,2 % → 97,9 % | 97,6 % | 76,34 → 83,94 |
| bulletin de paie | 64,3 % → 92,9 % | 100 % | 73,59 → 81,21 |
| relevé bancaire | 66,7 % → 91,7 % | 90,9 % | 83,50 → 86,69 |
| courrier administratif | 25,0 % → 90,0 % | 94,7 % | 75,40 → 88,64 |
| procuration | 83,3 % → 95,8 % | 100 % | 79,38 → 81,75 |
| tableau de paie | 83,3 % → 100 % | 100 % | 80,02 → 82,10 |
| document « scanné » | 57,1 % → 82,1 % | 80,8 % | 63,48 → 65,81 |

Le document « scanné » (bruit d'OCR simulé) reste le plus faible : le modèle
reprend moins bien les termes injectés quand la source est dégradée.

### 8.5 B (SHADOW) contre A, et déterminisme du moteur

* B n'a modifié ni l'objet d'options ni la requête envoyée au moteur :
  empreintes identiques sur **8/8** documents.
* Les sorties sont identiques sur 5/8 documents ; 3 diffèrent (courrier
  administratif DE, attestation EN, relevé bancaire EN).
* Sonde : le corps HTTP exact de la variante A du relevé bancaire EN a été
  capturé puis rejoué 6 fois directement (3 avec le cache de prompt, 3 sans) :
  les **7 sorties sont identiques entre elles** (296 jetons, identiques à B),
  alors que A, pendant la passe, avait produit 298 jetons.
* Conclusion : la différence ne vient pas du RAG mais de l'état du serveur
  d'inférence au moment de l'appel (cause exacte non élucidée ; hypothèse :
  historique du cache). Comparer des sorties entre deux passes comporte donc un
  bruit propre au moteur ; le critère de non-interférence de SHADOW est
  l'identité des requêtes (8/8), pas celle des sorties.

### 8.6 FR→EN

Le service de traduction ne transmet au moteur aucun bloc dont la langue source
est le français (il ne produit que du français). FR→EN n'est donc ni traduisible
ni mesurable de bout en bout : la variante C n'a rien envoyé (`NOT_SENT`, 8/8).
Les lignes FR→EN du référentiel sont importables et consultables (recherche
exacte et BM25) mais jamais injectées. Arbitrage demandé.

### 8.7 Défaut F-L2-02 : budget de jetons RAG inopérant (corrigé)

Avec `transformers` 5.19 (version épinglée), `apply_chat_template` renvoie un
objet `BatchEncoding` ; le compteur de messages du constructeur de contexte gelé
en prenait la longueur, soit **2 jetons par requête quelle que soit sa taille**.

* Côté RAG : le surcoût calculé par le pont valait toujours 0, donc le
  garde-fou `BUDGET_EXCEEDED` (800 jetons en ASSISTED, 1 500 en ACTIVE) ne se
  déclenchait jamais.
* Côté produit (fichier gelé, **non corrigé**) : le rognage du contexte avant
  envoi ne rogne jamais ; le contrôle préalable 32K, qui utilise un compteur
  correct, refuse alors la requête (`CONTEXT_OVERFLOW`) : pas de débordement
  silencieux, mais un refus là où un rognage était prévu.

Correctif (hors fichiers gelés, `rag_bridge.py`) : le gabarit de conversation est
rendu puis compté avec le compteur du service ; toute erreur de comptage donne
un refus `PROBE_FAILED`. Validation : plan rejoué sans traduction avec le
correctif → décisions et termes injectés identiques sur **32/32** documents ;
surcoût RAG mesuré 29 à 129 jetons (moyenne 79,8) contre écart d'usage réel du
moteur C − A de 29 à 131 jetons (moyenne 79,9). Les résultats de C ne sont pas
affectés : aucun document du corpus n'approchait le budget.

### 8.8 Défaut F-L2-03 : glossaire client écarté par la ponctuation (non corrigé)

Le filtre de pertinence du constructeur de contexte **gelé** découpe le bloc sur
les espaces seulement : un mot suivi d'une ponctuation (`Bruttogehalt:`) ne se
retrouve pas dans l'entrée, qui est retirée du contexte envoyé au moteur.

* **Glossaire client** : dans le bulletin de paie DE
  (`Bruttogehalt: 3.831,25 EUR`), l'entrée du glossaire client n'est jamais
  envoyée au moteur, en A comme en C. C'est le seul échec du glossaire (7/8).
  Défaut **antérieur au RAG**, présent en production : il peut toucher tout
  terme d'un seul mot collé à une ponctuation, lorsque aucun autre mot du
  segment ne se retrouve dans l'entrée (libellés « Terme: valeur », notamment
  en anglais, allemand, espagnol et arabe).
* **RAG** : 23 des 191 termes proposés par le RAG (12,0 %) ont été retirés par
  ce filtre ; ils expliquent 23 des 24 termes attendus non injectés (le
  vingt-quatrième est un vrai manque d'appariement, arabe).
* Correctif proposé : découpage sans ponctuation dans le constructeur gelé. Il
  modifie la fermeture d'empreinte historique et le comportement RUN29 : branche
  séparée, rejeu golden et **validation explicite** requis. Non appliqué au
  LOT 2.

## 9. Annotation humaine

Aucun annotateur n'a été mobilisé pendant le LOT 2 : la **fidélité sémantique
n'est pas mesurée**. Le protocole ([ANNOTATION-HUMAINE.md](../../docs/rag/ANNOTATION-HUMAINE.md))
et un paquet aveugle prêt à l'emploi (hors dépôt, textes synthétiques A et C
sous étiquettes `X`/`Y`, clé séparée) sont disponibles.

## 10. Non-régression

| Contrôle (mode DISABLED, arbre final) | Résultat |
|---|---|
| 34 fichiers de la fermeture d'empreinte historique | identiques à la référence Phase 0 |
| schéma OpenAPI | empreinte identique à la référence Phase 0 ; 18 chemins identiques |
| modules RAG chargés | aucun module `app.rag` ; pont RAG non chargé |
| corpus golden confidentiel (8 documents réels, hors dépôt) | **8/8 réussis** (20 min 04 s) ; comparé au golden du LOT 1 : 449/449 images PNG et 31/31 pages PDF identiques au pixel, 1 338/1 338 blocs OCR identiques (texte et confiance) ; 318 champs JSON différents, **tous** des chemins du répertoire temporaire d'exécution (aucune différence de contenu) |
| dépendances | 0 ligne modifiée |

## 11. Sécurité

* isolation tenant : toutes les requêtes BM25 sont filtrées en SQL par tenant
  (ou bibliothèque commune en lecture seule) ; tests d'isolation API sur la
  recherche lexicale, l'import et l'historique ; reconstruction d'index limitée
  au tenant de l'appelant ;
* import : taille et lignes bornées avant lecture complète, archive XLSX bornée
  (membres, tailles, ratio), DTD/entités refusées, formules refusées (XLSX et
  CSV), motifs d'instruction refusés, tout ou rien, aucune publication
  automatique ;
* trace d'import et journal de recherche : codes et compteurs seulement, aucun
  texte ; empreinte SHA-256 du fichier importé ;
* BM25 : résultats marqués `suggestion_non_injectable`, jamais transmis au
  constructeur de contexte ;
* rôles : import réservé au rôle d'édition du type de référentiel ;
  reconstruction d'index réservée à `rag_admin` ; lecture de l'historique et du
  diff réservée aux rôles RAG.

Contrôle anti-fuite avant publication (40 fichiers ajoutés ou modifiés) :
balayage des lignes ajoutées contre le corpus confidentiel (mots rares,
2/3/4-grammes, nombres, empreintes et noms des originaux, mentions
d'autorisation) et recherche ciblée de chemins locaux, adresses et ports
locaux, secrets, jetons, empreintes complètes et nom interdit. Résultat :
aucune empreinte, aucun nom ni aucune mention d'autorisation des originaux ;
45 signalements qualifiés manuellement comme faux positifs (formules
administratives universelles des gabarits synthétiques, tournures françaises
courantes, identifiants jetables de la base de test de la CI, année 2025) ;
0 chemin local, 0 secret, 0 occurrence du nom interdit.

## 12. Performance

| Mesure | Valeur |
|---|---|
| BM25, PostgreSQL 16, 20 000 entrées (58 475 postings, 19 Mo), 300 requêtes | p50 40,9 ms ; p95 66,1 ms ; max 95,3 ms |
| première version (sans statistiques précalculées) | p50 78,7 ms ; p95 104,4 ms |
| publication + indexation de 20 000 entrées | 9,2 s |
| plan d'exécution | utilise l'index (pas de parcours séquentiel des postings) |

| Mesure pendant la passe réelle | Valeur |
|---|---|
| Resolver C, CPU partagé avec le moteur | p50 59,8 ms ; p95 1 646 ms ; max 1 806 ms |
| Resolver C rejoué seul, sans moteur | p50 22,0 ms ; p95 26,6 ms ; max 30,4 ms |
| Resolver B (SHADOW) | p50 17,0 ms ; p95 43,5 ms ; max 280 ms |
| temps moyen de traduction par document | A 63,5 s ; B 54,6 s ; C 58,0 s (variance du moteur, pas un effet du RAG) |
| jetons d'entrée | +15,1 % en C (16 903 → 19 459) ; sortie +3,1 % |

La traîne du Resolver C vient de la concurrence CPU avec le serveur d'inférence
sur la même machine (6 cœurs) : au p95, 2,8 % du temps moyen de traduction
d'un document en C ; au maximum, 3,1 %.

## 13. Branche de maintenance (Pillow, Angular)

La correction des audits de dépendances reste dans une branche séparée, non
fusionnée (PR brouillon, CI réussie). Le LOT 2 ne modifie aucune dépendance ; sa
CI échouera donc sur les mêmes audits que le LOT 1 tant que la maintenance n'est
pas acceptée. Contrôle local **non poussé** : fusion éphémère LOT 1 +
maintenance + LOT 2 sans conflit ; `pip-audit --strict` et
`npm audit --audit-level=high` sans vulnérabilité. Sur cette fusion éphémère :
`ruff` sans remarque ; tests RAG LOT 1 + LOT 2 : 123 réussis, 2 ignorés
(PostgreSQL), 1 `xfail` attendu.

## 14. Limites

1. **Corpus synthétique uniquement** (choix de confidentialité) : aucune
   généralisation aux documents réels n'est démontrée.
2. **Aucun annotateur humain** : fidélité sémantique **non mesurée** ;
   références candidates non humaines ; chrF seulement indicatif. Le paquet
   aveugle (32 documents, 472 lignes) est prêt hors dépôt.
3. **Taxonomie de 10 domaines : proposition non validée** par le métier ; seuls
   5 domaines sont couverts par des documents du corpus.
4. **F-L2-03** non corrigé (fichier gelé) : glossaire client et 12,0 % des
   propositions RAG écartés quand le mot est collé à une ponctuation.
5. **F-L2-02 côté produit** non corrigé (fichier gelé) : refus 32K au lieu d'un
   rognage du contexte.
6. **FR→EN** non pris en charge par le pipeline.
7. **Moteur** : gpt-oss-20b non qualifié, sur CPU, environ 1 minute par document ;
   sorties non reproductibles d'une passe à l'autre malgré la température 0 ;
   une seule passe par variante.
8. **Linguistique** : clitiques arabes légers seulement, pas d'analyse
   morphologique ni de lemmatisation ; mots composés allemands non découpés ;
   un manque d'appariement arabe observé.
9. **BM25** : mesuré jusqu'à 20 000 entrées sur un PostgreSQL 16 local ; pas
   d'essai de charge concurrente.
10. **SHADOW** (F-L2-01) : avec la stratégie `drop`, une observation est perdue
    (et comptée) quand le courtier est indisponible.
11. **CI** : les audits pip/npm de la branche échouent tant que la branche de
    maintenance n'est pas acceptée (§13).

## 15. Suite

Le LOT 3 n'est pas commencé. Il ne le sera qu'après validation explicite.
Décisions attendues : validation (ou correction) de la taxonomie de domaines ;
correction de F-L2-03 dans une branche séparée (modifie l'empreinte
historique) ; mobilisation d'annotateurs ; arbitrage sur la traduction depuis le
français ; acceptation de la branche de maintenance.
