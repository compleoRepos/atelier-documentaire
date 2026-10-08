# Validation de laboratoire — 7 octobre 2026

## Résultat final

- Stack Compose privée réellement exécutée : PostgreSQL, Redis/Celery, MinIO avec SSE-S3 `AES256`, API et Angular/Nginx.
- Interface seule publiée sur `127.0.0.1:8080`. Services de données sur réseau interne.
- **14 contrôles du parcours HTTP réussis** : login/refus sans bearer, upload, analyse/traduction hors ligne via Celery, aperçus, revue attestée et Golden synthétique, persistance et téléchargements.
- **8 cas de charge réussis** : clients/pages `(1,1)`, `(1,10)`, `(1,50)`, `(1,100)`, `(1,200)`, `(10,1)`, `(50,1)`, `(100,1)`.
- Clients virtuels partageant une identité de fixture ; PDF natifs français synthétiques uniquement. Aucun original fourni n’est approuvé par ces tests.
- Aucun Qwen réel, téléchargement de poids ni inférence publique. OCR/LLM/GPU et CPU/mémoire détaillés non mesurés ; ne pas les remplacer par zéro.

## Preuves confidentielles, fournies séparément

`test-report/validation/container-result.json`, `load-results.json`, `load-case-*.json`, logs de construction/tests, et capture Chromium de la connexion. Les preuves et le corpus ne sont pas dans Git.

Le compte de fixture est généré aléatoirement dans un fichier temporaire `0600`, hors livrables. Les scripts ne contiennent ni mot de passe ni jeton de ce compte.

## Corrections vérifiées

Chemin Angular `browser/`, script shell MinIO mono-argument, passerelle Docker pour publication loopback, KMS DEV pour SSE-S3, queue `documents` commune producteur/worker, acteur d’audit transmis, résolution DNS Nginx après recréation API, et benchmark demandant effectivement la traduction après l’analyse.

Le KMS statique n’est utilisable qu’en DEV/QA. Ne pas écraser sa clé tant que des objets chiffrés existent. La banque doit utiliser un gestionnaire de clés audité, TLS et IAM à privilèges minimaux. Des corrections de firewall particulières au Sandbox ont été nécessaires ; ne pas les appliquer aveuglément ailleurs.

## Non accepté

Qualité OCR/français/sémantique/visuelle, NER exhaustif, signatures et cachets authentiques, GPU, SLO, pentest, déploiement Kubernetes bancaire et recette industrielle restent ouverts. `helm lint` et `helm template` sont des validations statiques seulement. Une réussite technique n’est pas une validation du contenu.
