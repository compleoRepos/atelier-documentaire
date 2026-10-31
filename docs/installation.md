# Installation

## Prérequis

- Python 3.12, Tesseract et langues `ara`, `deu`, `eng`, `fra`, `ita`, `nld`, `spa`.
- OCR par défaut : service `ocr-surya` (Surya OCR 2.5, `services/ocr-surya`) et ses poids GGUF vérifiés par SHA-256 — voir `docs/ocr/SURYA.md`. Tesseract n’est utilisé que sur sélection explicite (`TRANSLATOR_OCR_BACKEND=tesseract`).
- Node 22 et npm pour compiler Angular.
- Docker Compose v2 pour le laboratoire.
- Helm 3 et un cluster privé uniquement pour une validation d’installation réelle.

## Python local

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=backend
export TRANSLATOR_JWT_SECRET='secret local d’au moins 32 caractères'
python -m app.core.bootstrap
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Le mot de passe de bootstrap doit être fort et fourni par l’opérateur. Pour SQLite et l’exécution inline, ne pas réutiliser la configuration Compose/production. `create_all`/initialisation automatique éventuelle est limitée au laboratoire; utiliser des migrations contrôlées avant PostgreSQL de production.

## Installation hors ligne

Construire un wheelhouse depuis un miroir approuvé et transférer séparément les paquets OS, les modèles Tesseract, les éventuels modèles PaddleOCR et le tokenizer privé :

```bash
pip install --no-index --find-links /opt/wheels -r backend/requirements.txt
pip install --no-index --find-links /opt/wheels -r backend/requirements-ocr.txt  # optionnel
```

Les poids du modèle ne sont pas dans l’image API et ne doivent pas être téléchargés au démarrage. Définir `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1` et un chemin tokenizer local lisible par le worker. Aucun nom de modèle Qwen exact n’est affirmé dans ce dépôt.

## Compose

```bash
cp .env.example .env
# Remplacer toutes les variables ${...} par des valeurs de coffre local; ne pas commiter .env
docker compose config
docker compose up --build
```

Le `config` doit réussir avec des secrets réels. Le port publié par défaut est `127.0.0.1:8080`; les services de données n’ont pas de port hôte. MinIO est provisionné dans un bucket privé sans policy publique. L’endpoint IA privé, sa liste d’hôtes et le tokenizer sont obligatoires pour le chemin `private`.

Le profil local conserve les volumes nommés existants : ne pas lancer `docker compose down -v`, ne pas supprimer `postgres-data`, `minio-data`, `runtime-data` ou les clés hors dépôt. Le profil ClamAV est optionnel et non destructif :

```bash
docker compose --profile antivirus up --build
```

Pour un profil production, définir hors Git `TRANSLATOR_ENVIRONMENT=production`, `TRANSLATOR_ENGINE=private`, une URL HTTPS Qwen privée, `TRANSLATOR_PRIVATE_AI_ALLOWED_HOSTS` sans wildcard, un tokenizer monté et `TRANSLATOR_AV_SCAN_ENABLED=true` + `TRANSLATOR_AV_SCAN_REQUIRED=true`. L’image refuse de démarrer si ces conditions fail-closed ne sont pas satisfaites.

## Helm

Créer dans le coffre les Secrets nommés par `values.yaml` : URL PostgreSQL, URL Redis, accès S3, JWT et endpoint privé. Fournir la classe RWX et les CIDR des services privés. Puis valider :

```bash
helm lint infrastructure/helm/atelier-documentaire
helm template atelier-documentaire infrastructure/helm/atelier-documentaire > /tmp/atelier.yaml
```

L’installation DEV/PROD est manuelle, avec `KUBECONFIG`, approbation et `--wait`. Le dépôt ne l’exécute pas et ne peut pas confirmer la connectivité du cluster, les Secret, le TLS, le stockage RWX ou la capacité GPU. Une NetworkPolicy deny-by-default n’autorise que le DNS sélectionné, les CIDR/sélecteurs DB/Redis/S3 privés et les CIDR/sélecteurs Qwen explicitement configurés; aucun `0.0.0.0/0` n’est acceptable.
