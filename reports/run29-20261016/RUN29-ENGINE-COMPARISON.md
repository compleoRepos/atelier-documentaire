# RUN29 — Comparaison des moteurs : gpt-oss-20b local et Interim

> Question posée : « Si on utilise OpenAI gpt-oss-20b, ça marchera mieux ? » Réponse courte : **non démontré, et les indices disponibles sont défavorables.** Correctement découpé (F52), gpt-oss-20b fonctionne mécaniquement dans la chaîne (8/8 documents, 0 violation du budget 32K, 0 réponse finalement rejetée). Mais sur les 8 originaux il traduit et place **420 blocs contre 492** pour Interim, renvoie le texte source inchangé pour **150 blocs contre 83**, et provoque **6 défauts critiques d'entités** (entité protégée modifiée, entité ajoutée) **contre 0** ; il est aussi beaucoup plus lent sur la machine d'essai (≈ 110 s par requête sur 1 vCPU). Sa qualité de traduction n'est pas mesurée (0 référence humaine). **Il n'est pas qualifié et ne remplace pas Interim.**

## 1. Conditions contrôlées

| Élément | gpt-oss-20b | Interim |
|---|---|---|
| Modèle | `gpt-oss-20b`, poids officiels publiés par OpenAI (licence Apache 2.0), quantification MXFP4 au format GGUF ; empreintes SHA-256 des poids et du binaire vérifiées | fournisseur temporaire autorisé pour ces 8 originaux uniquement (autorisation privée, expirante, liste d'empreintes, hors Git) |
| Exécution | serveur `llama.cpp` local lié à `127.0.0.1` uniquement, **CPU**, 1 vCPU visible partagé avec les autres travaux, contexte 32 768, raisonnement `low`, sortie JSON contrainte par schéma | **mémoire** d'inférences réelles passées : **0 nouvelle requête** en RUN29 |
| Tokenizer du contrôle 32K | tokenizer officiel de gpt-oss-20b (révision épinglée, empreintes vérifiées) | o200k (inchangé) |
| Repli public | aucun ; aucun appel réseau hors de la machine | aucun |
| Code, IR, prompts, budgets, gardes | **identiques** pour les deux moteurs dans chaque comparaison (même copie figée du code, même IR, même budget d'entrée ~22 000 et de sortie ≤ 8 000 jetons, mêmes gardes d'entités et de JSON) | idem |
| Originaux | inchangés (empreintes vérifiées avant et après chaque passe) | idem |

Limite de cette comparaison : côté Interim, ce sont des réponses **enregistrées** lors d'inférences réelles antérieures, revalidées par les gardes actuelles ; côté gpt-oss, ce sont des inférences **nouvelles**. Les deux sont soumises aux mêmes contrôles, mais la comparaison ne mesure ni la qualité linguistique ni la latence de Interim.

## 2. Première passe complète : échec presque total (code F43–F47, sans F52)

| Document | Blocs | Traduits Interim (mémoire) | Traduits gpt-oss | Traduits par les deux | Cibles identiques (après casse/espaces) | gpt-oss : `model_returned_source` | gpt-oss : requêtes rejetées (réponse invalide) | gpt-oss : blocs de ces requêtes | gpt-oss : requêtes | Jetons entrée + sortie | Réservation max | Violations budget | Durée de traduction gpt-oss |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DOC-001 | 47 | 8 | 2 | 2 | 1 (1) | 8 | 1 | 6 | 2 | 1 343 + 946 | 11 633 | 0 | 186 s |
| DOC-002 | 24 | 9 | 0 | 0 | 0 (0) | 14 | 1 | 17 | 1 | 859 + 551 | 11 630 | 0 | 112 s |
| DOC-003 | 13 | 2 | 1 | 1 | 1 (1) | 0 | 0 | 0 | 1 | 321 + 136 | 11 092 | 0 | 41 s |
| DOC-004 | 229 | 97 | 0 | 0 | 0 (0) | 113 | 1 | 127 | 1 | 3 704 + 2 262 | 14 475 | 0 | 771 s |
| DOC-005 | 89 | 1 | 1 | 0 | 0 (0) | 4 | 0 | 0 | 2 | 706 + 568 | 11 145 | 0 | 106 s |
| DOC-006 | 418 | 272 | 0 | 0 | 0 (0) | 306 | 1 | 334 | 1 | 12 043 + 1 587 | 22 814 | 0 | 2161 s |
| DOC-007 | 178 | 95 | 0 | 0 | 0 (0) | 113 | 1 | 121 | 1 | 4 486 + 3 682 | 15 249 | 0 | 1000 s |
| DOC-008 | 74 | 23 | 1 | 1 | 1 (1) | 32 | 0 | 0 | 2 | 3 184 + 2 382 | 12 438 | 0 | 632 s |
| **Total (8 documents)** | 1072 | **507** | **5** | 4 | 3 | 590 | 5 | 605 | 11 | 26 646 + 12 114 | 22 814 | 0 | 5010 s |

gpt-oss n'a traduit que **5 blocs** contre 507 pour Interim. Ce n'était pas d'abord un problème de modèle : 605 blocs ont échoué parce que leur requête entière avait été rejetée.

### 2.1 Cause racine côté code : F52

Le mode Interim plafonnait déjà ses requêtes à 40 blocs et redécoupait une requête rejetée. Le mode moteur privé **n'avait ni plafond ni redécoupage** : il envoyait des requêtes de 121 à 334 blocs, et une seule réponse invalide (JSON mal formé, identifiants manquants, nombre de traductions incorrect, clé dupliquée) faisait rejeter tout le lot, conformément au principe d'échec fermé. F52 applique au moteur privé la même politique que Interim : 40 blocs au plus par requête et redécoupage borné (profondeur 5) en cas de contexte dépassé, de sortie invalide ou d'identifiants manquants. Le mode Interim est inchangé (rejeu `run29i` identique à `run29h`).

Sur les 5 petits documents, où les requêtes étaient déjà courtes (3 à 39 blocs), gpt-oss n'avait traduit que 5 blocs sur 128 envoyés : il renvoyait souvent la source telle quelle ou un JSON invalide. Cette partie relève du modèle, pas du découpage.

### 2.2 Deux défauts réels découverts en branchant le moteur privé : F46, F47

- **F46** : la dépendance `jinja2`, indispensable au rendu de tout gabarit de conversation, n'était pas déclarée. Le contrôle préalable du moteur privé était donc inutilisable dans l'image.
- **F47** (fail-open) : avec `transformers` 5, `apply_chat_template` renvoie un objet `BatchEncoding`. Le contrôle 32K comptait ses 2 clés au lieu des milliers de jetons réels : **la garde de budget ne bloquait rien.** Le comptage lit désormais `input_ids`, tout type inattendu est refusé, et un échec du contrôle préalable devient une anomalie critique **sans appel réseau**.

## 3. Repasse équitable sur DOC-004 avec F52

| Document | Blocs | Traduits Interim (mémoire) | Traduits gpt-oss | Traduits par les deux | Cibles identiques (après casse/espaces) | gpt-oss : `model_returned_source` | gpt-oss : requêtes rejetées (réponse invalide) | gpt-oss : blocs de ces requêtes | gpt-oss : requêtes | Jetons entrée + sortie | Réservation max | Violations budget | Durée de traduction gpt-oss |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DOC-004 | 229 | 89 | 90 | 86 | 24 (27) | 10 | 0 | 0 | 9 | 7 341 + 4 945 | 12 034 | 0 | 1077 s |

Sur le document le plus lourd en tableaux, gpt-oss passe de **0 à 90 blocs traduits** (Interim : 89), en 9 requêtes dont une redécoupée (`PRIVATE_CHUNK_SPLIT_RETRY`), sans aucune violation de budget. La garde d'entités a rejeté une traduction qui modifiait une entité protégée : la garde fonctionne aussi avec ce moteur. Les deux moteurs ne donnent la même cible que pour une petite partie des blocs traduits par les deux : ils traduisent différemment, et rien ne permet de dire lequel traduit mieux sans relecture humaine.

## 4. Passe finale complète avec F52 (8 documents)

Composition de la passe finale (même code F43–F52 pour les deux moteurs ; F53, ajouté ensuite, ne touche que le rendu) :

| Documents | Source gpt-oss | Remarque |
|---|---|---|
| DOC-001, DOC-002, DOC-003, DOC-005, DOC-007, DOC-008 | passe `run29oss3`, d'une traite | copie figée du code, empreinte vérifiée au début et à la fin |
| DOC-004 | repasse `run29oss2` (§ 3) | sa copie figée ne diffère de celle de `run29oss3` que par l'interrupteur F44, activé par défaut : comportement identique ; service de traduction et outils identiques |
| DOC-006 | `run29oss3`, **repris seul** | interrompu pendant la traduction (voir ci-dessous) ; **repris seul : rc=0, 2 521 s, originaux inchangés, empreinte de la copie figée identique au début et à la fin** |

Côté Interim : mémoire `run29i`, même code F43–F52, 0 requête.

**Incident de supervision (non lié au moteur).** La passe `run29oss3` a été arrêtée pendant la traduction de DOC-006 par l'arrêt automatique d'un terminal resté 2 h sans sortie : son lanceur redirigeait toute la sortie vers des fichiers. Les 6 documents déjà terminés n'étaient pas concernés. DOC-006 a été relancé seul sur **la même copie figée** (empreinte vérifiée), avec un dossier réinitialisé depuis la même IR, les mêmes options et un signal de vie périodique ; les empreintes des originaux ont été contrôlées avant et après. L'autorisation privée était valide au démarrage de la reprise (le lanceur la vérifie au démarrage ; aucune donnée ne quitte la machine avec ce moteur).

| Document | Blocs | Traduits Interim (mémoire) | Traduits gpt-oss | Traduits par les deux | Cibles identiques (après casse/espaces) | gpt-oss : `model_returned_source` | gpt-oss : requêtes rejetées (réponse invalide) | gpt-oss : blocs de ces requêtes | gpt-oss : requêtes | Jetons entrée + sortie | Réservation max | Violations budget | Durée de traduction gpt-oss |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DOC-001 | 47 | 7 | 4 | 4 | 2 (2) | 5 | 0 | 0 | 6 | 2 637 + 1 502 | 11 633 | 0 | 1008 s |
| DOC-002 | 24 | 8 | 9 | 8 | 3 (3) | 3 | 0 | 0 | 4 | 2 422 + 1 858 | 11 599 | 0 | 1330 s |
| DOC-003 | 13 | 2 | 1 | 1 | 1 (1) | 0 | 0 | 0 | 1 | 321 + 136 | 11 092 | 0 | 40 s |
| DOC-004 | 229 | 89 | 90 | 86 | 24 (27) | 10 | 0 | 0 | 9 | 7 341 + 4 945 | 12 034 | 0 | 1077 s |
| DOC-005 | 89 | 0 | 0 | 0 | 0 (0) | 5 | 0 | 0 | 2 | 706 + 256 | 11 145 | 0 | 380 s |
| DOC-006 | 418 | 268 | 247 | 239 | 45 (51) | 54 | 0 | 0 | 37 | 24 605 + 17 277 | 11 945 | 0 | 2469 s |
| DOC-007 | 178 | 95 | 68 | 64 | 14 (15) | 41 | 0 | 0 | 16 | 12 821 + 8 645 | 12 438 | 0 | 1560 s |
| DOC-008 | 74 | 23 | 1 | 1 | 1 (1) | 32 | 0 | 0 | 2 | 3 184 + 2 382 | 12 438 | 0 | 645 s |
| **Total (8 documents)** | 1072 | **492** | **420** | 403 | 90 | 150 | 0 | 0 | 77 | 54 037 + 37 001 | 12 438 | 0 | 8509 s |

**Lecture des résultats (8 documents, 1 072 blocs, même code, mêmes gardes, mêmes budgets).**

1. **Couverture : gpt-oss traduit et place moins de blocs.** 420 contre 492 pour Interim (mémoire), soit 72 de moins. 403 blocs sont traduits par les deux moteurs, 89 seulement par Interim, 17 seulement par gpt-oss, 563 par aucun (non traduisibles, déjà en français, OCR non fiable, refus de rendu, etc.). L'écart est concentré sur DOC-008 (23 contre 1), DOC-007 (95 contre 68) et DOC-006 (268 contre 247) ; DOC-002 et DOC-004 sont à parité (8/9 et 89/90).
2. **Cause principale : le modèle local renvoie le texte source inchangé.** `FAILED:model_returned_source` touche 150 blocs avec gpt-oss contre 83 avec Interim (DOC-008 : 32 contre 9 ; DOC-007 : 41 contre 17 ; DOC-006 : 54 contre 37), malgré le réessai prévu (`UNCHANGED_TRANSLATION_RETRY` : 29 blocs). Ces blocs conservent la source et partent en revue : aucun texte non traduit n'est présenté comme traduit.
3. **Intégrité des entités : signal négatif propre à gpt-oss.** 6 défauts critiques d'entités apparaissent avec gpt-oss et aucun avec Interim : 3 `PROTECTED_ENTITY_CHANGED` (DOC-004 : 1, DOC-006 : 2), 2 `CRITICAL_ENTITY_EXTRA` et 1 `HALLUCINATION_ENTITY_ADDED` (DOC-002). Les gardes les détectent et les blocs sont bloqués en revue, mais un modèle qui modifie ou ajoute des entités n'est pas acceptable sans contrôle humain.
4. **Le total plus bas d'alertes critiques (85 contre 101) n'est pas un gain de qualité.** Il vient de ce que gpt-oss produit moins de traductions à rendre, donc moins de défauts de rendu. DOC-005 : le seul bloc traduit par Interim y est refusé au rendu (8 alertes, 0 bloc placé) ; gpt-oss renvoie la source pour ce bloc, rien n'est rendu, 0 alerte. DOC-008 : 23 blocs placés par Interim contre 1 par gpt-oss, d'où 8 alertes contre 0. Les alertes de rendu (`RENDER_*` 30 contre 42, `RENDER_RULE_ERASED` 6 contre 10, `SCAN_TEXT_OVER_SOURCE_INK` 4 contre 8) baissent mécaniquement ; les alertes d'entités, elles, augmentent.
5. **Accord entre moteurs.** Sur les 403 blocs traduits par les deux, 90 cibles sont identiques (100 après normalisation de la casse et des espaces). La divergence ne dit pas lequel a raison : aucune référence humaine.
6. **Mécanique de la chaîne : conforme.** 77 requêtes, 0 réponse invalide finalement rejetée et 0 bloc perdu (9 réessais par découpage F52 relevés dans les résultats privés), **0 violation de budget**, réservation maximale 12 438 jetons pour un plafond de 32 768, originaux inchangés, provenance `NEW_MODEL_GENERATION` sur les 8 documents ; nom de modèle servi réduit à l'alias pour 7 documents, DOC-004 provenant de la repasse `run29oss2` servie sans alias (chemin local renvoyé par le serveur, expurgé des exports, OI-21).
7. **Coût et latence.** 54 037 jetons d'entrée et 37 001 de sortie ; 8 509 s de traduction cumulée (environ 2 h 22) sur 1 vCPU, soit environ 110 s par requête. Côté Interim, la passe réutilise la mémoire (0 requête) : les durées ne sont pas comparables.
8. **Effet de F52.** Sans découpage borné, la première passe ne traduisait que 5 blocs (§ 2) ; avec F52, 420. F52 est la correction qui rend le moteur privé mécaniquement utilisable ; elle ne le qualifie pas.

## 5. Ce que la comparaison ne prouve pas

- **Qualité linguistique** : non mesurée. 0 référence humaine ; un bloc « traduit » est un bloc accepté par les gardes, pas une traduction juste.
- **Performances de production** : les durées sont mesurées sur 1 vCPU partagé ; elles ne représentent pas un déploiement GPU (vLLM non testé, aucun GPU disponible).
- **Robustesse hors corpus** : 8 documents seulement.
- **Qwen** : aucun poids ni point d'accès disponible ; non testé.

## 6. Traçabilité

Chaque bloc porte sa provenance : moteur, mode de génération (`NEW_MODEL_GENERATION` ou `TRANSLATION_MEMORY_REUSE_ONLY`), modèle servi et usage de jetons. Deux réserves (OI-21) : la provenance porte encore le libellé historique `private-qwen-gateway` quel que soit le modèle privé ; et `llama.cpp`, lancé sans alias, renvoie un **chemin local** comme nom de modèle servi. Les passes `run29oss` et `run29oss3` ont été servies avec un alias imposé ; la repasse `run29oss2` (DOC-004) ne l'était pas. Les exports expurgent tout chemin.

## 7. Verdict moteur

| Question | Réponse |
|---|---|
| gpt-oss-20b remplace-t-il Interim ? | **Non.** Non qualifié |
| Fonctionne-t-il mécaniquement dans la chaîne ? | oui, depuis F46, F47 et F52 : gardes 32K actives, 0 violation de budget, garde d'entités active |
| Traduit-il mieux ? | qualité inconnue (0 référence humaine) ; indices mesurés **défavorables** : 72 blocs traduits de moins, 150 sources renvoyées contre 83, 6 défauts critiques d'entités contre 0 |
| Conditions de qualification | revue humaine d'un échantillon stratifié par langue et par type de bloc ; passe sur GPU (vLLM) avec mesure de latence ; taux de réponses invalides et de sources renvoyées au moins aussi bas que Interim ; provenance renommée et alias de modèle imposé par configuration |
