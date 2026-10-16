# Mode transitoire Interim — synthétique uniquement

## Décision explicite et périmètre

Le 8 octobre 2026, l’utilisateur a autorisé le mode temporaire **`engine=interim`**, distinct de `private`/Qwen et `offline`, puis décidé définitivement : **tester Interim uniquement sur des documents synthétiques non personnels**. Aucun texte, OCR, IR, image, métadonnée, extrait ou SHA des 8 PDF RH n’a été transmis au proxy. Leurs OCR/benchmarks restent locaux. **Traduction modèle des 8 originaux : `NOT_EXECUTED` par décision utilisateur ; Qwen privé : `NOT_AVAILABLE_IN_ENVIRONMENT`.**

Interim utilise le modèle réellement disponible au catalogue de ce runtime : **`gpt-5-mini`**, propriétaire OpenAI, encodeur réel **tiktoken `o200k_base`**. Sa fenêtre serveur est supérieure à 32K ; l’application ne relève jamais son plafond **32768**. Il ne s’agit ni de Qwen, ni d’un traitement dans le Private Cloud bancaire.

## Confidentialité et disponibilité

- Mode explicite seulement ; pas de fallback Qwen → Interim, Interim → offline ou service public caché.
- `production`/`prod` et environnement `private` refusent `engine=interim`.
- Avant construction du provider/réseau : SHA corpus réel denylisté, marqueur synthétique requis, allowlist SHA du **payload IR + tous contextes métier susceptibles d’être transmis**.
- Modifier texte/mémoire/glossaire/histoire après allowlisting invalide la permission. Marquer faussement un SHA réel comme synthétique ne contourne pas la denylist.
- Les SHA des **8 vrais originaux** ont été testés localement : `INTERIM_REAL_CORPUS_FORBIDDEN`, **0 requête**. Les valeurs SHA ne sont pas dans ce rapport/Git.
- Credentials : serveur/env seulement ; champs exclus de repr/model_dump, jamais code, Git ou client. Base HTTPS configurée, redirects refusés et `trust_env=False`.
- UI/API/audit indiquent le provider demandé Interim, modèle demandé/servi, hors Private Cloud et références non validées. Un gate bloqué affiche l’étape traduction en échec, jamais une fausse réussite.

## Contrat 32K : trois preuves distinctes

### 1. Barrière avant réseau

Chaque requête inclut système, JSON documentaire, contexte, glossaire, mémoire, entités/placeholders, décisions précédentes, chunk et schéma JSON strict. Comptage réel GPT + borne UTF-8 conservatrice + réserve de framing **4096 + 16 par message**, tous inclus dans l’entrée cible. Rejet ou chunking sémantique ; aucune découpe arbitraire de tableau.

`entrée complète ≤ 22000` + **`max_completion_tokens ≤ 8000` TOTAL** + `marge=2768` ≤ **32768**. La borne source est le [contrat officiel Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), vérifié pendant l’exécution :

> `max_completion_tokens`: An upper bound for the number of tokens that can be generated for a completion, including visible output tokens and reasoning tokens.

Le [guide reasoning](https://developers.openai.com/api/docs/guides/reasoning) confirme le principe de borne totale visible/reasoning/formatage pour les paramètres correspondants. Le compteur Interim n’est **pas** présenté comme un vrai tokenizer Qwen. `reasoning.effort=minimal`, selon le catalogue réel du proxy. `max_tokens` n’est plus envoyé ; température non imposée (paramètre non nécessaire/non compatible).

L’avertissement initial du skill sur le proxy a conduit à des sondes et un blocage provisoire. L’arbitrage explicite du coordinateur, confirmé par la documentation officielle et les sondes ci-dessous, l’a remplacé : **pas de blocage par défaut pour simple absence de preuve au catalogue**. Le contrat total est activé par défaut en DEV/TEST synthétique.

### 2. Conformité observée du proxy — synthétique uniquement

Demande : au moins 500 lignes de mots de test non personnels, pour forcer une troncature.

| Limite totale demandée | HTTP | Usage prompt/completion/total annoncé | Reasoning annoncé | finish_reason | Résultat |
|---:|---:|---|---:|---|---|
| 16 | 200 | 0 / 0 / 0 | 0 | length | rejeté ; compteurs nuls non exploitables pour calibration |
| 64 | 200 | 54 / 64 / 118 | 0 | length | cap atteint exactement, sortie rejetée |

Les deux requêtes sont bornées selon le contrat avant appel. **L’observation est limitée à ces sondes**, pas une preuve empirique universelle de toutes les futures générations. Le cas 16 n’est pas présenté comme une mesure fiable de consommation nulle. `length` n’a jamais produit une traduction acceptée.

### 3. Détection après appel et circuit

`usage` obligatoire et cohérent ; completion inclut reasoning (pas ajouté deux fois). Refus si `completion_tokens > limite`, `prompt_tokens + completion_tokens > 32768`, compteur serveur dépasse la borne locale ou somme incohérente : **`INTERIM_BUDGET_CONTRACT_VIOLATION`**, résultat rejeté et **circuit provider ouvert**, y compris pour la nouvelle instance de moteur du même endpoint/modèle dans le processus. Les appels suivants sont bloqués avant réseau par `INTERIM_TOTAL_GENERATION_CAP_NOT_VERIFIED`. En DEV/TEST multi-processus, chaque worker a son état ; ce mode reste interdit en production privée.

Usage absent/reasoning absent, finish `length`/content_filter/refusal/inconnu, modèle incorrect, JSON invalide ou IDs manquants/en trop/dupliqués : aucune traduction acceptée. La validation de budget est exécutée **même si finish=length**, pour ne pas masquer une violation derrière une troncature. Les écarts compteur local/bornes ↔ `prompt_tokens` serveur sont journalisés dans chaque chunk. Cette détection post-call **ne remplace pas** la barrière contractuelle pré-call.

## Passage réel du service sur fixture multilingue

Fixture écrite en code, sans personne réelle : 3 blocs anglais/arabe/espagnol → français, titre métier client « Attestation de travail », société/personne explicitement SYNTHETIC, date et référence fictives protégées.

Deux passages du service (dont lanceur versionné vérifiant son catalogue runtime) :

| Passage | Provider/modèle servi | Requêtes | Prompt | Completion totale | Total | Invariants |
|---|---|---:|---:|---:|---:|---|
| premier | Interim / gpt-5-mini | 1 | 385 | 145 | 530 | JSON/IDs, entités, date/référence et glossaire passés |
| lanceur versionné | Interim / gpt-5-mini | 1 | 385 | 144 | 529 | mêmes assertions passées |

Tous chunks ont une réserve ≤32768, usage total ≤32768 et completion ≤8000 ; reasoning est renseigné. La variation de sortie montre que ce modèle n’est pas déclaré bit-à-bit déterministe. **Référence humaine validée : false.** Ces invariants et assertions de 3 langues ne constituent pas une qualification linguistique bancaire.

Reproduction explicite, secrets déjà fournis au serveur :

```bash
PYTHONPATH=backend .venv/bin/python tools/interim_synthetic_acceptance.py --live
```

Le lanceur ne prend aucun chemin/document utilisateur en entrée et exige `--live`. Les réponses et telemetry synthétiques restent dans `test-report/prompt-1/` ignoré par Git. Les sondes préparatoires `max_tokens`/`reasoning:none` ont été conservées comme historique, **pas** comme preuve de l’implémentation finale utilisant `max_completion_tokens`.

## Retour à Qwen

Configurer explicitement `TRANSLATOR_ENGINE=private`, endpoint/modèle/version/tokenizer et allowlist privés correspondants. Ne pas réutiliser le compteur GPT pour Qwen. Relancer la recette privée, références humaines Golden et revue documentaire après merge Prompt 2. **Aucun switch automatique ni envoi des originaux à Interim ne sera effectué par ce code.**
