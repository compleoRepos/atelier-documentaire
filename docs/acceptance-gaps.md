# Écarts d’acceptation

Le socle livré respecte les interfaces documentées et fournit des contrôles techniques, mais **l’acceptation industrielle n’est pas acquise**. Chaque ligne ci-dessous doit recevoir une preuve dans l’environnement privé, sans publier le corpus.

| Écart | État actuel | Preuve attendue | Bloque |
|---|---|---|---|
| Références Golden | Aucun corpus humain validé commité; convention `dataset/expected/{source_sha256}/v{revision}.json` | Référence `approved`, reviewer, date, traductions/OCR facultatifs et audit | Gate stricte |
| CER/WER/OCR | Non mesurés sans vérité terrain | Annotations humaines par bloc/page, exclusions `unknown`, rapport reproductible | Qualité linguistique |
| Traduction/sémantique | Pas de modèle ni endpoint Qwen/vLLM privé fourni | Catalogue interne, tokenizer/poids mirrorrés, régression multilingue et revue humaine | Production AI |
| Layout / RTL | Reconstruction et diff à vérifier | Inspection originale/candidate/diff, tableaux, formulaires, signatures/cachets, pages quasi blanches | Finalisation |
| PaddleOCR | Option séparée, non incluse dans l’image API | Image worker validée, modèles locaux sans téléchargement et benchmark | OCR avancée |
| Charge | Aucun résultat production GPU | Campagnes 1/10/50/100 utilisateurs et 1/10/50/100/200 pages, matériel et p95 enregistrés | Sizing |
| Kubernetes | Templates Helm seulement | `helm lint/template`, installation DEV réelle, secrets externes, probes, NetworkPolicy et RWX vérifiés | Déploiement |
| Sécurité bancaire | Contrôles structurels, pas d’homologation | Pentest, revue IAM, rotation secrets, sauvegarde/restauration, egress et TLS approuvés | Mise en service |
| Migrations | SQLite/create_all limité au labo | Migrations PostgreSQL versionnées, rollback et reprise testés | Production DB |
| Observabilité | `/health` contractuel; `/metrics` non supposé | Instrumentation approuvée pour latences/OCR/LLM/GPU et alertes sans contenu | Exploitation |

## Règle de gate

`tools/verify_acceptance.py --strict` échoue si aucune référence validée, si les métriques requises sont nulles/non mesurées, ou si l’endpoint privé, son allowlist et le tokenizer local manquent. Un rapport technique offline ou un fixture synthétique ne peut pas servir de gate linguistique.

Le modèle privé exact, ses poids et son catalogue sont des dépendances de la plateforme et restent volontairement non spécifiés dans ce dépôt. Aucun cluster n’est déclaré déployé et aucun résultat de charge n’est inventé.
