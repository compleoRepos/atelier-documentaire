# Déploiement privé

- `compose.yaml` est destiné au laboratoire local; seule l’UI est publiée sur `127.0.0.1`. Le réseau Compose est `internal`.
- Les images MinIO et `mc` sont construites localement depuis les tags officiels épinglés dans `infrastructure/docker/`; aucun registre MinIO retiré n’est utilisé.
- Le mode `TRANSLATOR_ENGINE=offline` est la valeur par défaut. Le mode `private` échoue volontairement si endpoint, allowlist, modèle ou tokenizer ne sont pas préprovisionnés; aucun téléchargement de poids n’est effectué.
- Le chart déploie API, worker et frontend. PostgreSQL, Redis et S3/MinIO de production sont externes; leurs Secrets doivent exister avant installation avec les noms et clés exacts suivants:
  - `atelier-documentaire-database`: `TRANSLATOR_DATABASE_URL`, `TRANSLATOR_JWT_SECRET`;
  - `atelier-documentaire-redis`: `TRANSLATOR_CELERY_BROKER_URL`;
  - `atelier-documentaire-s3`: `TRANSLATOR_S3_BUCKET`, `TRANSLATOR_S3_ENDPOINT_URL`, `TRANSLATOR_S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`;
  - `atelier-documentaire-private-ai`: `TRANSLATOR_PRIVATE_AI_BASE_URL`, `TRANSLATOR_PRIVATE_AI_ALLOWED_HOSTS`, `TRANSLATOR_PRIVATE_AI_MODEL`, et facultativement `TRANSLATOR_PRIVATE_AI_API_KEY`.
  Aucun secret n’est fourni dans ce dépôt.
- Les PVC `external.tokenizerClaim` et `external.modelClaim` doivent être préremplies hors ligne et sont montées en lecture seule sur `/models/qwen-tokenizer` et `/models/qwen`. Le PVC `scratch` est RWX, partagé API/worker, monté sur `/app/runtime`; `/app/runtime/golden` est donc persistant et accessible par les deux.
- `fsGroup: 10001`, `runAsUser: 10001`, root filesystem en lecture seule et NetworkPolicy deny-by-default sont intentionnels. Renseigner les CIDR ou sélecteurs privés exacts pour DB, Redis, S3 et le service IA; ne jamais ajouter `0.0.0.0/0`.

Validation sans cluster:

```bash
helm lint infrastructure/helm/atelier-documentaire
helm template atelier-documentaire infrastructure/helm/atelier-documentaire --set ingress.host=example.invalid >/tmp/atelier.yaml
```

Ces commandes ne prouvent ni la validité des Secrets externes, ni la classe RWX, ni l’installation Kubernetes. Le déploiement DEV/PROD reste une étape manuelle avec `KUBECONFIG`, approbation et tests de santé. Aucun cluster n’est contacté par la validation locale.

## Méthodes et limites

- `compose.yaml` est un laboratoire conservateur : volumes nommés conservés, API/worker/frontend non-root, root filesystem en lecture seule, `tmpfs` et limites CPU/mémoire. `--profile antivirus` ajoute ClamAV sans supprimer de données.
- `infrastructure/docker/production-entrypoint.sh` refuse le mode offline, les endpoints AI publics/loopback, les wildcards CORS/allowlist et l’AV non obligatoire lorsque `TRANSLATOR_ENVIRONMENT=production`.
- `tools/ops_backup.py` sauvegarde réellement `pg_dump` et chaque objet S3 vers une destination neuve, enregistre des SHA-256 et n’expose aucune valeur secrète dans le manifeste. `tools/ops_restore.py` valide tous les hashes puis restaure uniquement vers un DSN et un bucket/prefix de quarantaine explicitement distincts. `--dry-run` signifie `planned`, pas `success`.
- `tools/release_gate.py` exige une attestation privée structurée avec métriques, reviewer, provenance et couverture. Les fixtures publiques ne peuvent pas satisfaire la promotion PROD.

La validation Helm (`helm lint`/`helm template`) n’établit pas que les Secrets, PVC RWX, TLS, GPU, ClamAV, DNS ou CIDR privés existent. Aucun cluster bancaire, achat, secret, original ou résultat privé n’est contacté ou versionné. Le test Kind reste à exécuter par un opérateur disposant de Docker et d’une capacité suffisante; l’absence de Kind n’est pas transformée en réussite Kubernetes.
