# Release gate et attestations

## Principe fail-closed

`tools/release_gate.py` refuse DEV/TEST/PROD dès qu’une preuve structurée manque. Une simple variable `approved=true`, un nom de fichier ou un succès de dry-run ne suffit jamais. PROD exige une attestation JSON **privée**, hors de l’arbre Git, issue des fixtures Golden privées autorisées par l’opérateur.

Exemple de commande (la preuve n’est jamais committée) :

```bash
python tools/release_gate.py --environment production \
  --proof /opt/translator/attestations/release-2026-01.json \
  --repository-root "$PWD"
```

Le JSON doit contenir `schema: release-attestation/v1`, `evidence_class: private-golden`, `synthetic_only: false`, une approbation avec `reviewer`, `approved_at`, `ticket`, `decision: approved`, les cinq métriques mesurées (`ocr_score`, `translation_score`, `semantic_score`, `layout_score`, `visual_score`), `critical_entity_errors: 0`, `hallucination_errors: 0`, `provenance.sources` non vide et `coverage` entre 0 et 1. Les seuils par défaut sont OCR .95, traduction .90, sémantique .95, layout .90 et visuel .90; `--thresholds` permet de fournir une politique versionnée.

Le résultat JSON contient `status`, `errors`, `quality_score`, `provenance`, `coverage` et `reviewer`. Toute erreur sort avec un code non nul. La gate ne déploie rien et ne configure aucun environnement bancaire.

## Environnements

- **CI publique** : lint, tests, scans et build sur fixtures publiques uniquement. Les JSON Golden privés, secrets, originaux et rapports complets sont exclus.
- **DEV/TEST/PROD** : workflow manuel + environments protégés et reviewers configurés par l’opérateur. Le dépôt ne crée pas l’environnement GitHub et ne déclenche pas de cloud bancaire.
- **PROD** : `TRANSLATOR_ENGINE=private`, Qwen/tokenizer provisionnés hors ligne, allowlist privée et endpoint HTTPS. Le mode offline est explicitement refusé par le garde-fou de l’image.

### Contrat de configuration production

Le profil `production` est fail-closed dans `app.core.settings.Settings` et dans
l'entrypoint de l'image. L'opérateur doit fournir via le coffre ou les Secrets
de l'environnement (jamais dans Git) :

- `TRANSLATOR_AUTO_CREATE_SCHEMA=false`, `TRANSLATOR_AUTH_MODE=cookie`,
  `TRANSLATOR_COOKIE_SECURE=true` et un JWT d'au moins 64 caractères ;
- `TRANSLATOR_ENGINE=private`, `TRANSLATOR_PRIVATE_AI_BASE_URL=https://...`,
  `TRANSLATOR_PRIVATE_AI_ALLOWED_HOSTS` explicite sans wildcard/loopback,
  `TRANSLATOR_PRIVATE_AI_MODEL`, `TRANSLATOR_PRIVATE_AI_MODEL_VERSION`,
  `TRANSLATOR_TOKENIZER_PATH` et, si requis par l'endpoint, la credential
  `TRANSLATOR_PRIVATE_AI_API_KEY` ;
- `TRANSLATOR_STORAGE_BACKEND=s3`, un `TRANSLATOR_S3_ENDPOINT_URL=https://...`
  privé, `TRANSLATOR_S3_BUCKET`, région et credentials S3/KMS externes ;
- `TRANSLATOR_AV_SCAN_ENABLED=true`, `TRANSLATOR_AV_SCAN_REQUIRED=true`, un
  endpoint ClamAV privé, et `TRANSLATOR_METRICS_TOKEN` non vide ;
- des `TRANSLATOR_ALLOWED_ORIGINS` exclusivement HTTPS et des certificats TLS
  gérés par l'opérateur pour l'IA privée, S3, l'Ingress et les services
  externes. PostgreSQL doit être pré-migré : aucun `create_all` en production.

La workflow manuelle `manual-release-gate` ne déploie rien : elle attend le
secret d'environnement `RELEASE_ATTESTATION_JSON`, exécute la gate structurée
et utilise les environnements GitHub protégés `dev`, `test` et `production`.
Les reviewers, secrets, TLS et règles de protection sont à configurer par
l'opérateur ; aucune connexion bancaire n'est créée par le dépôt.

## Limites connues

La preuve ne peut pas inventer un score quand un endpoint, un poids ou une référence est absent. La qualité visuelle, les performances GPU et la recette Qwen réelle restent non prouvées sur une machine publique; elles doivent être mesurées sur le runner privé autorisé. Une approbation humaine ne remplace pas la couverture ni la provenance.
