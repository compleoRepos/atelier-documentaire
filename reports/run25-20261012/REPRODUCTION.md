# RUN25 — Reproduction

Ce document décrit comment reproduire les résultats de run25 à partir du dépôt. Les données des documents
(originaux, OCR, IR, sorties) ne sont pas dans Git : les étapes 3 à 5 exigent l'accès privé au corpus et une
autorisation du propriétaire en cours de validité.

## 1. Environnement

| Élément | Valeur utilisée |
|---|---|
| Système | Ubuntu 24.04 (sandbox) |
| Python | 3.12.3, environnement virtuel avec `backend/requirements.txt` et pytest 9.1.1 |
| OCR | Tesseract (moteur local), `OMP_THREAD_LIMIT=1` pour les traitements lourds |
| Frontend | Node.js 22, `npm ci` |
| Code | branche `feature/run25-recette-finale-20261012`, empreinte `f4a84aaef38c7c7d` |

L'empreinte du code se calcule depuis la racine du dépôt :

```bash
find backend/app tools -name "*.py" -not -path "*/__pycache__/*" | LC_ALL=C sort \
  | xargs sha256sum | sha256sum | cut -c1-16
```

## 2. Tests (sans données privées)

```bash
# Backend, périmètre exact de la CI
PYTHONPATH=backend pytest backend/tests/unit backend/tests/integration backend/tests/e2e \
  backend/tests/regression backend/tests/security --junitxml=test-report/ci.xml

# Tests de régression run25 seuls (synthétiques)
PYTHONPATH=backend pytest backend/tests/unit/test_run25_regressions.py -q

# Analyse statique et dépendances
ruff check backend tools
pip-audit -r backend/requirements.txt --strict

# Frontend
cd frontend && npm ci && npm run typecheck && npm test && npm run build && npm audit --audit-level=high
```

Le golden local (`PYTHONPATH=backend pytest backend/tests/golden_dataset`) requiert le corpus privé, placé sous
`dataset/input`, que Git ignore.

## 3. Run du corpus (privé, sous autorisation)

Le lanceur versionné `tools/interim_owner_corpus_run.py` traite les originaux d'un répertoire privé. Il refuse toute
requête au moteur IA si l'autorisation est absente, expirée ou ne liste pas l'empreinte SHA-256 du document.

```bash
OMP_THREAD_LIMIT=1 PYTHONPATH=backend python tools/interim_owner_corpus_run.py --live \
  --authorization <autorisation-privee.json> \
  --input-dir <originaux-prives> \
  --out-dir <sortie-privee> \
  --timeout 300 \
  --reuse-analysis \
  --translation-cache <sortie-du-run-de-reference> \
  --only DOC-00N            # répétable ; sans --only, les 8 documents
```

* `--reuse-analysis` reprend l'OCR et l'IR copiés dans le répertoire de sortie. Le verdict run25 a repris ceux de
  run24, produits par le même code OCR.
* `--translation-cache` sert une traduction mémorisée **uniquement** quand la signature de contenu du bloc est
  identique. Tout autre bloc part vers le moteur IA sous la garde de 32K. Le verdict run25 n'a envoyé aucune
  requête.
* Le run supplémentaire run25-live a été obtenu avec la même commande, sans `--translation-cache`.
* Le script privé de chaque run écrit, avant traitement, l'empreinte du code et le HEAD dans `logs/FINGERPRINT.txt`,
  puis l'état de fin dans `logs/STATUS.txt`.
* Les copies de la baseline sont rendues inscriptibles. Les sources restent en lecture seule.

## 4. Mesures (sorties hors dépôt)

Les trois outils refusent d'écrire dans le dépôt.

```bash
# Mesure v2.1 : couverture attendue, tentée, écrite, partielle et absente, rendu mesuré dans le PDF
PYTHONPATH=backend:tools python tools/recette/measure_v2.py \
  --run baseline=<base> --run run17=<r17> --run run24=<r24> --run run25=<r25> \
  --out <prive>/v21.json

# Registre d'anomalies (une ligne par bloc défectueux, avec page et coordonnées)
PYTHONPATH=backend:tools python tools/recette/anomaly_register.py \
  --run run24=<r24> --run run25=<r25> --out <prive>/register.json

# Planches multi-runs et audit des régions graphiques
PYTHONPATH=backend:tools python tools/recette/compare_runs_sheets.py \
  --run baseline=<base> --run run17=<r17> --run run24=<r24> --run run25=<r25> --dest <prive>/sheets
```

Les exports anonymisés `metrics/*.json` de ce répertoire sont dérivés de ces sorties par un générateur privé. Ce
générateur ne garde que des compteurs, des identifiants abstraits et des géométries, et il échoue si un motif
interdit apparaît : texte, nom de fichier, empreinte de document ou chemin privé.

## 5. Contrôles privés complémentaires

Ces contrôles ne sont pas versionnés, parce qu'ils manipulent le contenu réel :

* relecture instrumentée du rendu (décisions par bloc, zéro requête) ;
* mesure du débord de masque (encre originale effacée hors des blocs écrits) ;
* mesure de continuité des filets ;
* comparaison des séquences de chiffres source/cible ;
* recadrages comparatifs.

Leurs résultats agrégés figurent dans les rapports, et leurs sorties dans l'archive privée de preuves.

## 6. Confidentialité

Ne doivent jamais être versionnés ni partagés publiquement :

* originaux, OCR, IR, PDF produits, images, planches et recadrages ;
* noms de fichiers et empreintes des documents ;
* autorisation du propriétaire, secrets et poids de modèle ;
* journaux contenant du contenu.

Avant chaque commit sont contrôlés :

* `git diff --check` ;
* l'audit anti-fuite privé : motifs interdits, et recouvrement de 4-grammes avec le texte OCR réel ;
* la liste des fichiers non suivis.
