# IA privée et traduction honnête

Le service `app.ai.translation.service.translate_blocks` reçoit l’IR documentaire et ne contacte jamais un fournisseur public. Il conserve sa signature historique et retourne une map `translations` compatible pipeline. Il ajoute `translation_telemetry` et place aussi cette télémétrie dans `ir['_translation_telemetry']`; aucune mémoire tenant n’est stockée globalement.

## Modes

- `offline` utilise uniquement les correspondances exactes du glossaire client fourni par l’appelant et les entrées de mémoire marquées `validated: true`. Une map mémoire/glossaire provenant de l’API est déjà considérée comme validée; les listes doivent porter le marqueur explicite. Un bloc français est conservé tel quel. Tout bloc inconnu reste inchangé, reçoit `UNTRANSLATED` (`severity: error`) et est compté comme couverture non native inconnue, jamais comme traduction réussie.
- `private` utilise `PrivateQwenEngine`, un endpoint OpenAI-compatible privé (`/chat/completions`). Le tokenizer local est obligatoire et chargé avec `local_files_only=True`; aucun téléchargement de poids ou d’endpoint n’est effectué implicitement.

## Sécurité de la passerelle

L’hôte est une correspondance exacte de `private_ai_allowed_hosts`. Les adresses DNS sont contrôlées avec `ipaddress`; toute adresse publique est refusée. Le nom est re-résolu immédiatement avant chaque requête afin de détecter une modification DNS. Le client HTTP utilise `trust_env=False`, `follow_redirects=False` et un timeout explicite. Une erreur, une redirection, une re-résolution publique ou une réponse non conforme bloque le chunk; il n’y a aucun fallback silencieux vers le texte source présenté comme traduit ni vers un modèle public.

Une éventuelle sonde standalone doit utiliser seulement un texte synthétique réservé, par exemple un bloc `probe-001` ne contenant aucune donnée utilisateur. Elle vérifie santé, allowlist, résolution et contrat JSON; elle ne constitue pas une recette Qwen réelle. Aucun endpoint Qwen réel n’a été fourni ou appelé dans les tests.

## Contexte et sortie

Les budgets par défaut sont `max_context=32768`, `target_input=22000`, `max_output=8000` et `safety_margin=2768`. `max_context` est un plafond dur et `max_output` ne peut pas dépasser 8000. La prévalidation du moteur compte le rendu réel de `apply_chat_template(..., tokenize=True, add_generation_prompt=True)`, les messages, une réserve du schéma de réponse et la sortie projetée; tout dépassement devient `CONTEXT_OVERFLOW` sans requête.

Les tableaux et unités atomiques restent entiers. Un tableau ou paragraphe supérieur au budget n’est pas découpé au milieu: il devient `CONTEXT_OVERFLOW` / `REVIEW_REQUIRED` et sa source est conservée. Le builder sélectionne seulement les fragments de contexte pertinents et bornés; il ne transmet jamais toute la mémoire.

Le message système contient seulement les instructions. Le JSON documentaire, y compris un texte pouvant contenir « ignore previous instructions », est placé dans le message utilisateur comme données non fiables. La sortie doit être exactement `{"translations":[{"id":"...","text":"..."}]}` avec les mêmes identifiants, cardinalité et ordre. Les clés JSON dupliquées sont rejetées, comme les identifiants manquants, supplémentaires ou dupliqués et `finish_reason=length`.

Les nombres, dates, coordonnées, références, emails, téléphones et entités critiques explicitement fournies sont remplacés par des marqueurs uniques. Une collision, disparition, duplication ou modification bloque le bloc en erreur critique et restaure sa source. Les invariants automatiques déclarent leur couverture: un libellé comme `Date: 2024` peut légitimement rester inchangé et n’est pas une preuve qu’un nom de société doit être modifié.

## Mémoire et options

`DocumentMemory` est une projection caller-supplied et tenant-scoped (`document_type`, `domain`, `language`, `style`, terminologie/décisions). Le retrieval est fragmentaire et contextuel. Le système sépare toujours ces données du message système. Le client peut fournir `client_glossary_priority=True`, une mémoire validée, un glossaire validé, les versions de ces entrées, un tokenizer double et un transport HTTPX de test.

La télémétrie expose la version servie quand la passerelle la renvoie, le modèle demandé, le hash d’identité du tokenizer chargé localement, la version de prompt, les versions d’entrées (`glossary_version`, `memory_version`, `tokenizer`), l’usage prompt/completion/total, la latence totale et par chunk, ainsi que la couverture et les erreurs.

## Tests

Les tests privés utilisent un tokenizer synthétique local et `httpx.MockTransport` (ou un serveur HTTP local de test). Ils ne téléchargent aucun poids et ne font aucun appel réseau public. Les tests ne déclarent pas avoir validé un vrai tokenizer Qwen ni un endpoint réel; la recette bancaire/GPU/Qwen demeure une étape explicite ultérieure.
