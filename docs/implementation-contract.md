# Contrat d’implémentation interne

Base : dépôt de travail initial (chemin local non publié).
Diagnostics : Python ruff + pytest ; Angular compilateur strict/tsc. Aucun projet d’hébergement Interim initialisé : cible explicitement privée.

## Propriété des fichiers

- Moteur documentaire : `backend/app/domain/`, `backend/app/documents/`, `backend/app/ai/`, `backend/tests/unit/`, `backend/tests/golden_dataset/`, `backend/tests/regression/`, `tools/analyze_dataset.py`, `tools/golden_report.py`.
- API/persistance : `backend/app/core/`, `backend/app/infrastructure/`, `backend/app/application/`, `backend/app/api/`, `backend/app/workers/`, `backend/app/main.py`, `backend/tests/integration/`, `backend/tests/e2e/`, `backend/tests/security/`.
- Angular : tout `frontend/`.
- Déploiement/documentation : Dockerfiles, Compose, Helm/Kubernetes, CI, documentation (sauf fichiers du corpus déjà produits), `backend/pyproject.toml`, requirements, README, `tools/load_test.py`.
- Parent : plan, TODO, corrections d’intégration, rapport final, archives et PR.

## Moteur documentaire

Module `app.documents.pipeline` expose :

```python
def analyze_document(source_path: str, work_dir: str, options: dict | None = None) -> dict: ...
async def translate_document(ir: dict, work_dir: str, options: dict | None = None) -> dict: ...
def reconstruct_document(ir: dict, translations: dict[str, str], output_path: str, protected_regions: list[dict] | None = None) -> dict: ...
def evaluate_document(ir: dict, translations: dict[str, str], render_result: dict | None = None, reference: dict | None = None) -> dict: ...
```

L’analyse écrit `analysis.json`, `previews/original-NNN.png`. IR JSON contient : `schema_version`, `source_path`, `format`, `language`, `languages`, `document_type`, `domain`, `pages`, `tables`, `warnings`, `versions` ; une page : `number` (1-based), `width`, `height`, `scanned`, `blocks`. Un bloc : `id` unique global, `page`, `kind`, `text`, `bbox` (points PDF), `font_size`, `confidence` (0..1), `language`. Les champs supplémentaires sont permis. Les cellules peuvent référencer des blocs. `warnings` inclut les limites OCR/manuscrit/signatures/cachets/structure scannée et les langues mixtes. L’IR DOCX garde une liaison non destructive aux nœuds du conteneur source.

`translate_document` reçoit options : `engine` ('offline' ou 'private'), `private_ai_base_url`, `private_ai_allowed_hosts` (liste), `private_ai_model`, `private_ai_api_key` facultative, `tokenizer_path`, `max_context`=32768, `target_input`=22000, `max_output`=8000, `safety_margin`=2768, `glossary` (liste source/target/domain), `memory` (dict source->target), `protected_entities` (liste strings), `protected_regions` (liste page/bbox). Renvoie JSON : `translations` (bloc_id->texte), `issues` (liste dict code/severity/message/block_id?), `quality` (dict), `versions`, `untranslated_blocks` (liste). Écrit `translation.json`. Aucun appel public ; moteur privé refuse endpoint/tokenizer non explicitement autorisés. Hors ligne, français source conservé / mémoire exacte / glossaire exact, sinon segment conservé et flag UNTRANSLATED. Jamais prétendre avoir traduit l’inconnu.

`reconstruct_document` renvoie `output_path`, `issues`, `pages_preserved`, `layout_score` (géométrique seulement). Réécrit un fichier candidat, pas l’original. PDF et images => PDF ; DOCX => DOCX. Écrit les aperçus traduit et diff lorsque possible. Ne doit pas gommer les zones protégées ; texte intersectant ces zones reste inchangé avec issue. Les erreurs de débordement restent bloquantes.

`evaluate_document` renvoie `critical_entity_errors`, `untranslated_blocks`, `layout_score`, `visual_score`, `ocr_score`, `translation_score`, `semantic_score`, `issues`, `status` ('REVIEW_REQUIRED' par défaut). Les métriques non mesurables sont null. Les erreurs critiques et l’absence de revue empêchent FINAL.

## API `/api`

Authentification bearer JWT :
- POST `/auth/login` {username,password} -> {access_token,token_type,user:{id,username,tenant_id,role}}.
- GET `/auth/me` -> user.
- GET `/dashboard` -> {documents,review_required,approved,failed,engine,metrics}.
- POST `/documents` multipart file -> document, enfile analyse.
- GET `/documents` -> liste.
- GET `/documents/{id}` -> {id,filename,status,created_at,language,document_type,domain,page_count,quality,issues,analysis?,translation?}.
- POST `/documents/{id}/analyze` / `/translate` -> document ; exécution job.
- GET `/documents/{id}/artifact/{kind}` : `original`, `candidate`, `final`, `analysis`, `translation` ; final autorisé seulement APPROVED. Downloads authentifiés.
- GET `/documents/{id}/preview/{kind}/{page}` : kind original/translated/diff, page 1-based.
- POST `/documents/{id}/review` {action:'approve'|'reject'|'correct', corrections:{block_id:texte}, protected_entities:[], protected_regions:[{page,bbox}], comment, attest_review:boolean, promote_golden:boolean} -> document. `approve` exige reviewer/admin, attestation, revalidation des corrections, aucune erreur critique ni segment inconnu ni overflow. Golden explicitement choisi, référence versionnée et auditée. Pas de corrections implicites lors de l’approbation.
- GET/POST `/glossary` [{id,source,target,domain,version}] ; POST {source,target,domain}.
- GET/POST `/memory` [{id,source,target,validated,version}] ; POST reviewer {source,target} validé humainement.
- GET `/testing` -> {dataset_available,documents,tests_passed,tests_failed,metrics,reference_status} sans scores fictifs.
- GET `/audit` -> [{id,action,document_id,user_id,timestamp,details}], tenant limité.
- GET `/admin` -> configuration non secrète et capacités ; admin seulement.
- GET `/health` sans auth -> état processus, distinct de `/api/admin`.

Statuts : UPLOADED -> ANALYZING -> ANALYZED -> TRANSLATING -> REVIEW_REQUIRED -> APPROVED ou REJECTED ; FAILED en cas d’erreur. L’API ne doit pas marquer APPROVED d’elle-même. Contrôle tenant avant accès quel que soit l’ID. Références Golden seulement via revue explicite. Auth bootstrap CLI `python -m app.core.bootstrap` avec env et mot de passe fort fourni ; aucun compte par défaut. Production fail-closed pour secret absent, pas d’auth header libre.

Persistences : DATABASE_URL SQLAlchemy (sqlite labo, PostgreSQL prod), STORAGE_BACKEND local ou s3 privé, DATA_DIR, JWT_SECRET, EXECUTION_MODE inline ou celery, CELERY_BROKER_URL Redis. Variables préfixées `TRANSLATOR_`. API/worker partagent stockage privé et DB ; Celery queue d’IDs, pas contenu personnel. La fonction worker relit tenant/doc depuis DB. Audit ne doit jamais enregistrer texte ou mots de passe.

## Frontend

Angular standalone, strict, pas de services distants ni CDN. Pages `/login`, `/dashboard`, `/documents`, `/upload`, `/documents/:id`, `/review/:id`, `/glossary`, `/translation-memory`, `/admin`, `/testing`, `/audit`. HTTP API même origine proxy `/api`, token bearer ; afficher les métriques null « Non mesuré ». Aucun faux dataset ou pourcentage. Revue : sélecteur page, trois panneaux originaux/traduit/diff via blobs authentifiés, liste blocs avec corrections, cases de validation explicites et promotion Golden optionnelle. Polling borné uniquement des jobs utilisateur en cours, stopper sur erreur/terminal/destruction composant. `interim-routes.json` correspond exactement aux routes existantes.
