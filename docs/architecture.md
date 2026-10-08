# Architecture

## Flux de traitement

```text
Navigateur --HTTPS/TLS--> Ingress/Nginx --> frontend
                                      \--> API FastAPI --> PostgreSQL (métadonnées/audit)
                                                       \--> S3 privé (originaux/candidats/aperçus)
                                                       \--> Redis --> worker Celery
                                                                       \--> OCR local / pipeline
                                                                       \--> endpoint IA privé allowlisté
```

Le navigateur ne parle jamais directement à PostgreSQL, Redis, S3 ou au modèle. Les uploads/downloads sont authentifiés et tenant-scoped. Le worker reçoit des identifiants de job, puis relit tenant et document depuis la base; le contenu documentaire n’est pas placé dans Redis.

## Contrats de données

Le pipeline produit une IR avec version de schéma, format, langues, pages, blocs, tables, avertissements et versions. Chaque bloc porte un identifiant global, page, type, texte, bbox en points PDF, taille, confiance et langue. Les traductions sont indexées par `block_id`; les blocs inconnus restent explicitement non traduits. Le module doit respecter les signatures de `docs/implementation-contract.md`.

Les états sont monotones et auditables : `UPLOADED → ANALYZING → ANALYZED → TRANSLATING → REVIEW_REQUIRED → APPROVED|REJECTED`; `FAILED` est terminal d’erreur. L’API ne passe jamais seule à `APPROVED`. Toute approbation exige rôle, attestation, revalidation, absence d’erreur critique, d’inconnu et de débordement.

## Stockage et isolation

- PostgreSQL de production est externe au chart et référencé par Secret.
- S3/MinIO est privé, bucket non anonyme; originaux immuables et artefacts versionnés.
- RWX sert au scratch et aux previews partagées entre API et worker; les artefacts durables doivent rester dans S3.
- L’audit contient action, tenant, utilisateur, horodatage et détails minimisés; jamais texte, mot de passe ou token.
- Secrets de production ne sont ni dans Git, ni dans `values.yaml`, ni dans les logs.

## OCR, langues et rendu

Tesseract est installé avec `ara/deu/eng/fra/ita/nld/spa` et une police DejaVu unicode. PaddleOCR est optionnel dans `requirements-ocr.txt`, à installer dans un worker/image dédiée avec modèles mirrorrés localement. Signatures, cachets, manuscrits, RTL, tableaux et chevauchements exigent une revue humaine; aucune calibration n’est prétendue.

La reconstruction écrit un candidat, préserve dimensions/pages et bloque les débordements. `layout_score` est géométrique seulement. CER/WER, score OCR, traduction ou sémantique sont `null` sans référence humaine validée.

## IA privée

L’adaptateur accepte un endpoint privé explicitement configuré, une allowlist d’hôtes et un tokenizer local. La fenêtre totale est plafonnée à 32768 tokens (`target_input`, `max_output`, marge). Il n’existe aucun appel public ni téléchargement au runtime. Le catalogue privé doit fournir l’identifiant et les poids; ce dépôt ne garantit pas un modèle Qwen exact. vLLM peut être déployé séparément avec image validée, PVC `/models`, variables HF offline et endpoint OpenAI-compatible interne.

## Sécurité d’exécution

Images non root, filesystem racine en lecture seule côté Helm, `tmp` en `emptyDir`, capacités Linux supprimées, service account sans auto-montage de token, ingress TLS. Les NetworkPolicies refusent par défaut puis autorisent DNS et CIDR privés déclarés pour DB/Redis/S3/Qwen. Les chemins `/metrics` ne sont pas supposés : aucun probe ni documentation ne les invente.
