# Références techniques consultées

## MinIO / chiffrement

- [Référence officielle Server Side Encryption Settings](https://docs.min.io/aistor/reference/aistor-server/settings/server-side-encryption/) : `MINIO_KMS_SECRET_KEY` accepte `<key-name>:<base64-32byte-key>`. Une clé statique implémente un sous-ensemble du KMS, sans rotation ; elle est destinée aux tests et à l’évaluation uniquement. Un gestionnaire KMS/KES est requis pour la production. Une seule famille de paramètres KMS doit être active.
- [Publication MinIO RELEASE.2025-10-15T17-29-55Z](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z). Source compilée et commit vérifié dans `infrastructure/docker/minio.Dockerfile` ; compilation du programme racine, pas de l’archive Go `./cmd`.
- [Publication mc RELEASE.2025-08-13T08-35-41Z](https://github.com/minio/mc/releases/tag/RELEASE.2025-08-13T08-35-41Z). Source et commit vérifiés dans `infrastructure/docker/mc.Dockerfile`.

Ces références documentent la configuration et la provenance, pas une validation de sécurité bancaire ni une conformité de licence. Les binaires compilés depuis les sources peuvent afficher une version de développement ; le commit source et l’ID d’image sont les preuves utilisées.
