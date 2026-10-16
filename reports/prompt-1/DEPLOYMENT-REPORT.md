# Livraison et déploiement — Prompt 1

## Livraison source

- Dépôt privé : `compleoRepos/atelier-documentaire-prive`.
- Branche exclusive : `feature/prompt-1-industrialisation-20261008`.
- Base commune : `6fb913a3a402e45c5813bf343fb85f26ef0e0e20`.
- Commit de code : `b7e40a0223d6db00af494427a542ba8646be080a`.
- Identité auteur/committer conforme à l’instruction de l’utilisateur, vérifiée avant commit.
- **Aucun merge, force-push ou changement de main.** Aucune modification/cherry-pick de la branche Prompt 2. Le coordinateur reste responsable du merge final.
- Dépendances installées uniquement dans `.venv` et `frontend/node_modules` de ce worktree. Aucun volume, port, symlink ou Docker de l’autre exécution n’a été modifié.

Le SHA du commit de rapports/signal final est donné dans la réponse de livraison. `EXECUTION-RESULT.json` porte le commit de code testé ; un fichier ne peut pas inclure son propre SHA Git sans circularité. Vérifier le HEAD distant au merge.

## Configuration ajoutée et prérequis techniques

`TRANSLATOR_IMAGE_PREPROCESSING_PROFILE` : `auto` (défaut), `clean_scan`, `noisy_scan`, `old_document`, `mobile_photo`, `complex_document`. Le choix manuel invalide est rejeté par le pipeline, pas accepté silencieusement. `opencv-python-headless==4.13.0.92` ajouté aux dépendances backend principales ; aucun modèle téléchargé. Tesseract/OSD et langues OCR doivent être provisionnés localement. Les bbox source de l’IR et les régions protégées doivent être consommées par la reconstruction de Prompt 2, sans double transformation.

TIFF : validation frames/MIME/magic/pages/pixels, analyse multipage et adaptateur de copie PDF. Cet adaptateur ne remplace pas le renderer de fidélité ; conserver ses raccords au merge.

## Vérifications exécutées

- Ruff et compileall backend/tools.
- Suite Python technique complète (unitaires/intégration/E2E/non-régression/sécurité), tests géométriques et E2E scan réel.
- Angular typecheck, tests, build, audit npm.
- Audit pip strict.
- OCR local des 8 originaux/31 pages, dégradations contrôlées, passage corpus final sur code corrigé ; résultats définitifs dans TEST-REPORT et IMAGE-PREPROCESSING-REPORT.
- CI source : [Private document translator](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/37760420819). Elle exécute aussi PostgreSQL/migrations, Compose/Helm et builds Docker ; son résultat observé, sans prédiction, est dans TEST-REPORT.

Le sandbox n’a pas de Docker : les tests conteneurs locaux ne sont donc pas revendiqués. Les services CI utilisent leurs noms/volumes propres au runner GitHub, sans données bancaires. Pas de déploiement d’application ni d’ouverture publique des documents.

## Déploiement bancaire : BLOQUÉ, volontairement

| Élément | Statut |
|---|---|
| Endpoint/model Qwen privé autorisé, clé, allowlist | NOT_AVAILABLE_IN_ENVIRONMENT |
| Tokenizer Qwen réel local correspondant au modèle servi | NOT_AVAILABLE_IN_ENVIRONMENT |
| Poids Paddle/embedding privés si retenus pour la production | NOT_AVAILABLE_IN_ENVIRONMENT |
| Transcriptions/traductions/rubriques Golden humaines | NOT_AVAILABLE_IN_ENVIRONMENT |
| Baseline et tenant Golden privés | NOT_AVAILABLE_IN_ENVIRONMENT |
| Runner/cloud bancaire et contrôles réseau/KMS/AV | non attestés / non provisionnés dans cette exécution |
| Intégration des améliorations renderer Prompt 2 | responsabilité du coordinateur, non fusionnée ici |
| Approbation de release protégé | non demandée ni exécutée ; gate existant conservé |

Les modes stricts existants, network policies et gates privés ne sont pas désactivés. Aucun fallback public ou modèle fictif n’est utilisé pour obtenir un PASS. **Ne pas promouvoir cette branche seule en production bancaire.**

## Vérification après merge par le coordinateur

1. Fusionner les interfaces décrites dans MERGE-INTERFACES.md, notamment bbox source, matrices inverses, enhanced snapshots et adaptateur TIFF.
2. Relancer la suite technique et tout le corpus réel après le merge, car le renderer sera différent.
3. Provisionner les assets privés et références humaines, puis lancer la recette `bank-private-acceptance` autorisée et le gate manuel adéquat.
4. Faire revoir les signatures/cachets, l’OCR des identifiants et la fidélité linguistique/documentaire avant toute promotion.

Ces points sont des prérequis de qualification, pas une action automatique ou un déploiement promis.

## Mode transitoire non production

engine=interim activable seulement DEV/TEST sur fixtures codées/allowlistées. Credentials serveur/env (champs exclus), gpt-5-mini runtime vérifié, tiktoken0.12.0/o200k_base, total max_completion_tokens8000 + entrée22000 + marge2768. Aucun envoi des8PDF RH ; traduction réelle NOT_EXECUTED par décision utilisateur. Compteurs/circuit/trace providerInterim expliqués dans INTERIM-TRANSITION.md. Retour explicite engine=private avec assetsQwen correspondants, jamais automatique.
