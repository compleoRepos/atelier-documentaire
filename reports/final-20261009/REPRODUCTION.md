# REPRODUCTION — reproduire les tests et la recette corpus (09/10/2026)

Ce document décrit comment reproduire **exactement** les résultats des rapports de `reports/final-20261009/`. Il ne contient aucun chemin privé : `$PRIVATE` désigne un répertoire hors dépôt, en accès restreint (`chmod 700`), où se trouvent les originaux, l’autorisation propriétaire et toutes les sorties.

## 1. Version exacte

- **Branche** : `feature/industrialisation-finale-20261009`.
- **Commit** : celui qui contient ces rapports (`git log -1`). Un commit ne peut pas contenir son propre SHA.
- **Empreinte du code exécuté par le passage final** : `f69a6210b29e8196`. Le lanceur l’enregistre dans `$PRIVATE/run17/logs/FINGERPRINT.txt`, avec la valeur `fingerprint=` : SHA-256 tronqué de la concaténation triée des `sha256sum` de `backend/app/**/*.py` et `tools/**/*.py`. Elle se recalcule ainsi :

  ```bash
  find backend/app tools -name "*.py" -not -path "*/__pycache__/*" | LC_ALL=C sort \
    | xargs sha256sum | sha256sum | cut -c1-16
  ```

  Une empreinte différente signifie que le code a changé depuis le passage. Les métriques ne s’appliquent alors plus telles quelles.

- **Empreinte du code committé** : `f2d0950f03f0d780`.
  - Différence avec l’empreinte exécutée : la seule docstring d’en-tête de `backend/app/documents/line_verification.py`. Deux valeurs réelles citées en exemple y ont été retirées (audit de confidentialité).
  - Son AST, docstrings exclues, est identique à la version exécutée : le comportement est le même.
  - La version exécutée de ce fichier est conservée en privé (`$PRIVATE/pre-scrub/line_verification.run17.py`) pour la vérification.

## 2. Dépendances et configuration

| Élément | Version / valeur utilisée | Rôle |
|---|---|---|
| Python | 3.12 (venv) | backend, outils |
| Dépendances Python | `backend/pyproject.toml`, extra `[test]` (`pytest`, `pytest-asyncio`, `ruff`) | — |
| PyMuPDF (`fitz`) | version du venv (`pip show pymupdf`) | rendu et reconstruction PDF |
| Tesseract | 5.x, langues `ara deu eng fra ita nld spa osd` | OCR des scans |
| LibreOffice | `soffice` headless | DOCX → PDF (pagination) |
| Node.js / npm | 22 / npm (`package-lock.json`) | frontend Angular |
| `OMP_THREAD_LIMIT=1` | obligatoire pour les passages lourds | évite la saturation de Tesseract (D7) |
| Modèle de développement | Interim (`gpt-5-mini`, tokenizer `o200k_base`) | traduction temporaire |
| Budget de contexte | entrée ≤ 22 000, sortie ≤ 8 000, marge 2 768, total ≤ 32 768 | garde moteur, fail-closed |
| Qwen privé | **non disponible** (endpoint, tokenizer, poids) | production future, interface conservée |

**Aucune configuration supplémentaire n’est versionnée.** Trois éléments restent hors Git :

- **l’autorisation propriétaire Interim** : un JSON listant les SHA-256 exacts des originaux, avec une date d’expiration ;
- **les originaux** ;
- **les sorties.**

Sans autorisation valide, le fournisseur Interim refuse **avant tout appel réseau** (`interim_guard.py`).

## 3. Tests techniques (sans données privées)

```bash
cd atelier-documentaire-prive
python -m venv .venv && . .venv/bin/activate && pip install -e "backend[test]"   # ou le venv existant
ruff format --check backend tools && ruff check backend tools
OMP_THREAD_LIMIT=1 PYTHONPATH=backend python -m pytest -q -p no:cacheprovider backend/tests \
  --ignore=backend/tests/golden_dataset --junitxml=junit-technical.xml
```

- Les tests ajoutés pendant la mission finale sont listés dans `TEST_REPORT.md` §2.
- Ils n’utilisent que des rasters et des textes synthétiques créés dans le code de test.
- Les tests `test_final_regression_gaps.py::test_real_second_reading_under_highlight` exigent le vrai binaire Tesseract.

**Frontend :**

```bash
cd frontend && npm ci && npm run typecheck && npm test && npm run build && npm audit --omit=dev
```

## 4. Corpus golden (8 originaux, moteur hors ligne)

Le corpus golden rejoue les 8 originaux avec le moteur de traduction **hors ligne**, sans aucun appel au modèle. Il lit le catalogue privé `dataset/metadata/catalog.json` et les originaux placés dans `dataset/input/`. Ces deux emplacements sont ignorés par Git. Les références humaines approuvées éventuelles se trouvent dans `dataset/expected`, avec la variable `TRANSLATOR_GOLDEN_TENANT_ID`. Si un original est absent, son cas est **ignoré (skip)** et n’est jamais compté comme PASS.

```bash
OMP_THREAD_LIMIT=1 PYTHONPATH=backend python -m pytest -v -p no:cacheprovider backend/tests/golden_dataset
```

## 5. Passage corpus Interim (originaux, autorisation propriétaire)

### 5.1 Lanceur

`tools/interim_owner_corpus_run.py` :

| Option | Effet |
|---|---|
| `--live` | obligatoire : envoie les originaux autorisés à Interim |
| `--authorization FICHIER` | autorisation propriétaire hors Git |
| `--input-dir` | répertoire des originaux |
| `--out-dir` | sorties privées ; le lanceur refuse un chemin du dépôt |
| `--only DOC-00x` | option répétable |
| `--timeout` | délai par requête, en secondes |
| `--reuse-analysis` | réutilise l’OCR/IR déjà produit (même SHA), **réapplique la vérification des lignes** (D19), envoie de **nouvelles** requêtes Interim, puis reconstruit et évalue |
| `--reuse-translations` | réutilise les traductions déjà obtenues, sans aucune requête |

La console n’affiche que des identifiants, des compteurs et des codes d’anomalie.

### 5.2 Séquence du verdict final (run17)

1. **Analyse complète** (run10), c’est-à-dire l’OCR et l’IR sur le code final d’OCR :

   ```bash
   OMP_THREAD_LIMIT=1 PYTHONPATH=backend python -u tools/interim_owner_corpus_run.py --live \
     --authorization "$PRIVATE/owner-authorization.json" --input-dir "$PRIVATE/originaux" \
     --out-dir "$PRIVATE/run10/out" --timeout 300
   ```

2. **Verdict** (run17). Copier `analysis.json`, `preprocessing/` et les aperçus `original-*` / `enhanced-*` de run10 vers `$PRIVATE/run17/out/DOC-00x/`, puis lancer en 3 groupes parallèles au plus (`OMP_THREAD_LIMIT=1`, `nice`) :

   ```bash
   OMP_THREAD_LIMIT=1 PYTHONPATH=backend python -u tools/interim_owner_corpus_run.py --live \
     --authorization "$PRIVATE/owner-authorization.json" --out-dir "$PRIVATE/run17/out" \
     --timeout 300 --reuse-analysis --only DOC-007
   ```

   Groupes utilisés :
   - A : `DOC-007` ;
   - B : `DOC-006 DOC-001` ;
   - C : `DOC-002 DOC-003 DOC-004 DOC-005 DOC-008`.

   Chaque document produit, dans son répertoire privé :
   - `analysis.json` ;
   - `translation.json`, qui contient la télémétrie par requête : tokens réservés et consommés, borne 32K ;
   - `candidate.pdf` ;
   - `evaluation.json` ;
   - `summary.json` ;
   - les aperçus.

## 6. Mesures et planches comparatives

Les deux outils refusent d’écrire dans le dépôt.

```bash
# Métriques strictes (couverture stricte / écrite / texte, OCR du texte source résiduel,
# zones visuelles en union avec la référence, anomalies dédupliquées)
PYTHONPATH=backend python tools/recette/measure_corpus_metrics.py "$PRIVATE/baseline-617" baseline \
  --dest-dir "$PRIVATE/metrics" --ocr --union-with "$PRIVATE/run17/out"
PYTHONPATH=backend python tools/recette/measure_corpus_metrics.py "$PRIVATE/run17/out" run17-final \
  --dest-dir "$PRIVATE/metrics" --ocr --union-with "$PRIVATE/baseline-617"

# Planches original / ancienne traduction / nouvelle traduction / différences, et audit des zones visuelles
PYTHONPATH=backend python tools/recette/compare_visual_sheets.py \
  "$PRIVATE/baseline-617" "$PRIVATE/run17/out" "$PRIVATE/comparisons/run17-vs-baseline"
```

Les rapports versionnés ne reprennent que des **compteurs anonymisés** (`CORPUS_METRICS_FINAL.json`). Les métriques détaillées et les planches contiennent des données personnelles : elles restent dans l’archive privée.

## 7. Contrôles avant commit

```bash
git diff --check
git status --short    # aucun PDF, analysis.json, OCR, image, autorisation, .env ou sortie
```

Le `.gitignore` exclut les extensions et répertoires de données. L’audit de fuite du commit final est consigné dans `TEST_REPORT.md` §5.
