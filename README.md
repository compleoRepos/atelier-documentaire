# Atelier documentaire — comprendre, traduire, vérifier

Projet Git autonome `atelier-documentaire-prive`. Le développement et les tests ont été isolés de l’application BTP, qui n’est pas modifiée.

Les commits de ce projet utilisent **Hamza NORDINE** comme auteur et committer, avec l’adresse noreply du compte GitHub authentifié.

> **MVP technique exécutable, recette industrielle bancaire NON validée.** Les huit PDF fournis sont traités techniquement, mais les seuils OCR, linguistiques et visuels ne sont pas démontrés. Le mode hors ligne ne transforme pas un texte étranger inconnu en traduction française.

## Composants livrés

- Angular/TypeScript : authentification, documents, upload, détail, revue original/candidat/diff, glossaire, mémoire, administration, QA et audit.
- FastAPI/Pydantic/SQLAlchemy : JWT, tenants et rôles, contrôles d’upload, versions, revue attestée, audit et OpenAPI.
- Python : IR page/bloc/table, OCR Tesseract local, reconstruction PDF/DOCX, images de comparaison, contrôles numériques et de débordement.
- Moteur IA interchangeable : endpoint **privé** compatible vLLM, hôtes autorisés, tokenizer local, budget complet ≤32 768 tokens. Aucun fallback public.
- PostgreSQL, Redis/Celery (queue `documents`), stockage S3 chiffré, MinIO de laboratoire et Nginx.
- Golden Framework, gates de recette et de baseline, tests unitaires/intégration/E2E/sécurité/régression, Dockerfiles et Helm.

**Limites fonctionnelles importantes :** PaddleOCR n’est pas le moteur exécuté ici ; sa calibration nécessite une image et des poids privés. Détection des langues/types encore heuristique, signatures/cachets et zones manuscrites à annoter humainement, pagination DOCX logique plutôt qu’un rendu Word certifié. Les scores sémantiques, linguistiques et visuels complets doivent encore être implémentés/calibrés et validés : `null` n’est jamais un PASS.

## Démarrage Docker DEV

Prérequis : Docker/Compose et Python 3.12+. Dans ce dossier :

```bash
python3 tools/create_dev_env.py --out .env
# Le générateur refuse d’écraser un fichier existant et n’affiche aucun secret.
docker compose config -q
docker compose up --build -d
# Premier administrateur : nom explicite et saisie interactive du mot de passe.
docker compose exec -e TRANSLATOR_BOOTSTRAP_USERNAME=admin api python -m app.core.bootstrap
```

Interface locale : **http://127.0.0.1:8080**. Seule l’interface est publiée ; API, PostgreSQL, Redis et S3 restent sur le réseau interne. Le frontend possède un réseau de passerelle distinct car Docker 29 ne publie pas les ports d’un réseau uniquement `internal`.

Le générateur crée une clé KMS statique **DEV uniquement** pour que le chiffrement SSE-S3 `AES256` fonctionne. Conserver cette clé tant que des objets chiffrés existent. En banque, utiliser un KMS/KES/Vault géré, des identités applicatives à privilèges minimaux, TLS et un filtrage réseau bancaire ; ne pas utiliser les credentials root ni la clé statique de ce laboratoire en PROD.

Le mode initial est `offline` : réutilisation de texte français et de mémoire/glossaire validés, sinon `UNTRANSLATED` et `REVIEW_REQUIRED`. Pour Qwen : fournir `TRANSLATOR_ENGINE=private`, endpoint privé, allowlist, identifiant/version du modèle et **tokenizer correspondant aux poids servis**, monté en lecture seule. Aucun poids n’est téléchargé implicitement.

## Installation Python directe

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=backend
export TRANSLATOR_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export TRANSLATOR_BOOTSTRAP_USERNAME=admin
python -m app.core.bootstrap
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Cette variante SQLite/inline est locale, pas une preuve PostgreSQL/Kubernetes. Pour une installation sans Internet, utiliser un wheelhouse et des registres internes, et fournir localement les modèles OCR/tokenizers.

## Vérifications

```bash
PYTHONPATH=backend ruff check backend tools
PYTHONPATH=backend pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security
# Corpus confidentiel fourni séparément, jamais dans GitHub :
PYTHONPATH=backend pytest backend/tests/golden_dataset
python tools/golden_report.py --out test-report
python tools/verify_acceptance.py --root .
python tools/compare_baseline.py --baseline /chemin/prive/baseline-approuvee.json
cd frontend && npm ci && npm run typecheck && npm test && npm run build
```

La gate de recette **doit échouer** sans preuves, modèle et références privées ; la comparaison de baseline renvoie `NOT_EVALUATED` si la baseline manque. Les tests techniques ne certifient ni le français ni l’absence d’hallucinations.

## Documentation et confidentialité

- [Architecture](docs/architecture.md), [contrat des modules](docs/implementation-contract.md), [installation](docs/installation.md).
- [Exploitation](docs/operations.md), [guide utilisateur](docs/user-guide.md), [IA privée](docs/private-ai.md), [écarts d’acceptation](docs/acceptance-gaps.md).
- [Infrastructure](infrastructure/README.md) et [OpenAPI](docs/openapi.json).
- [Guide de déploiement détaillé](docs/deploiement.md) : laboratoire Docker Compose (validé de bout en bout), Kubernetes/Helm, profil production fail-closed, écarts connus G1–G11, vérifications et exploitation.
- Inventaire, corpus et rapport QA fournis dans l’archive **confidentielle séparée**. Ils sont exclus de Git et des contextes Docker.

`helm lint`/`helm template` vérifient les manifests ; aucun cluster bancaire n’a été installé. Aucun déploiement PROD n’est réalisé ni permis par une réussite technique seule. Valider également les licences de PyMuPDF, MinIO et des poids IA avec les responsables compétents.
