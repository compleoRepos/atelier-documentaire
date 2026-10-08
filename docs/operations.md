# Exploitation

## Démarrage et vérification

1. Vérifier les Secret hors Git, l’allowlist IA, le tokenizer local, les accès PostgreSQL/Redis/S3 et l’espace RWX.
2. Déployer DEV manuellement avec Helm et attendre les probes `/health` (API) et `/healthz` (frontend).
3. Créer explicitement un compte via `python -m app.core.bootstrap`; aucun compte par défaut.
4. Tester login, upload d’un fixture non sensible, analyse, traduction privée ou mode offline explicite, revue et téléchargement final.
5. Contrôler que `APPROVED` n’est atteint qu’après attestation humaine. Un modèle indisponible ou une référence absente doit produire une revue/échec, jamais un succès simulé.

## Exploitation des jobs

Le worker Celery consomme la queue `documents`. Redis ne contient que des IDs. En cas d’échec, consulter l’identifiant du document et l’audit, sans copier texte ou fichier dans les logs. Rejouer uniquement après avoir vérifié l’idempotence du pipeline et la présence des artefacts privés. Les originaux sont immuables; un retry écrit une nouvelle version candidate.

## Données et sauvegardes

Sauvegarder PostgreSQL (métadonnées/audit), S3 (originaux/artefacts), et la configuration de coffre. Tester la restauration dans un tenant de quarantaine. Ne pas inclure les PDFs ou sorties dans les logs CI, tickets ou rapports publics. Le RWX est un espace de travail : il ne remplace pas la sauvegarde S3.

Les commandes opérables sont `tools/ops_backup.py` et `tools/ops_restore.py`. Elles écrivent un manifeste `atelier-backup/v1` avec la taille et le SHA-256 du dump PostgreSQL et de chaque objet S3, en flux borné (pas de chargement massif en mémoire) :

```bash
python tools/ops_backup.py --destination /secure/backup/$(date -u +%Y%m%dT%H%M%SZ) \
  --postgres-dsn "$TRANSLATOR_DATABASE_URL" --s3-bucket "$TRANSLATOR_S3_BUCKET" \
  --s3-prefix documents/
python tools/ops_backup.py --dry-run --destination /secure/backup/next \
  --postgres-dsn "$TRANSLATOR_DATABASE_URL" --s3-bucket "$TRANSLATOR_S3_BUCKET"
```

Un dry-run retourne `state: planned`, jamais `success`, et n’écrit pas de dump. Une restauration commence par la validation de tous les hashes et exige une destination PostgreSQL et un bucket/prefix S3 isolés, puis `--confirm`; le script refuse les identités source et n’utilise ni `--clean` ni `--create` :

```bash
python tools/ops_restore.py --backup-dir /secure/backup/ID --destination /secure/restore/ID \
  --target-postgres-dsn "$QUARANTINE_DATABASE_URL" \
  --target-s3-bucket quarantine-documents --target-s3-prefix restore/ID --dry-run
python tools/ops_restore.py --backup-dir /secure/backup/ID --destination /secure/restore/ID \
  --target-postgres-dsn "$QUARANTINE_DATABASE_URL" \
  --target-s3-bucket quarantine-documents --target-s3-prefix restore/ID --confirm
```

Le test de restauration doit utiliser une base et un bucket de quarantaine, ainsi que des données synthétiques générées hors Git; il ne doit jamais pointer vers la banque ou vers les volumes Compose existants. Conserver seulement le `restore-result.json` anonymisé et ses hashes dans un espace de preuve privé.

## Sécurité

Renouveler JWT, DB, Redis, S3 et endpoint AI via le coffre. Vérifier régulièrement l’allowlist et les NetworkPolicies. Toute sortie réseau inattendue est un incident : couper le worker/API, préserver l’audit minimal, analyser les logs sans exfiltrer le contenu, puis révoquer les secrets. Les images doivent rester non root, offline pour les modèles et sans privilèges.

ClamAV est optionnel en laboratoire mais la production doit publier `TRANSLATOR_AV_SCAN_ENABLED=true`, `TRANSLATOR_AV_SCAN_REQUIRED=true` et un endpoint privé; l’image backend refuse sinon. Les en-têtes CSP, HSTS, anti-clickjacking et `nosniff` sont posés par Nginx/Ingress. Les réglages `av_scan_*` sont transmis au backend afin que le branchement applicatif puisse les consommer sans changement de contrat d’exploitation.

## Observabilité et capacité

`/health` vérifie effectivement la base, le stockage et la queue ; une dépendance inaccessible produit HTTP 503. `/metrics` expose les mesures HTTP et stages sans identifiant personnel dans les labels ; protéger son accès par `TRANSLATOR_METRICS_TOKEN` en production. Les logs d’échec de stage donnent seulement le stage et la classe d’exception, jamais son message ni le contenu du document. `tools/load_test.py` mesure une campagne synthétique bornée. Les valeurs OCR/LLM/GPU restent `null` lorsque l’instrumentation ne les fournit pas ; ne pas convertir un test local en capacité démontrée du modèle privé à 100 utilisateurs/200 pages.

## Rollback et migration

Conserver l’image précédente et le schéma compatible avant `helm upgrade`. En cas de régression, arrêter les jobs nouveaux, revenir à l’image précédente avec Helm et reprendre après validation des migrations. Ne pas supprimer les originaux ni rétrograder la base sans procédure approuvée. PostgreSQL de production exige des migrations versionnées; la création automatique de tables est réservée au laboratoire.

Appliquer explicitement `python -m alembic -c backend/alembic.ini upgrade head` avant le démarrage (dans l’image : `/app/backend/alembic.ini`). Désactiver `TRANSLATOR_AUTO_CREATE_SCHEMA` hors laboratoire ; API et worker refusent de démarrer si la révision Alembic requise est absente. Tester la migration puis la sauvegarde/restauration sur des bases isolées avant une promotion ; un downgrade destructeur n’est jamais une étape automatique de production.
