# Dataset documentaire et statut Golden — Prompt 1

## Originaux privés vérifiés

Les originaux ont été récupérés via la pièce jointe privée autorisée de la tâche de référence, dans ce sandbox propre. Aucun URL privé n’est reproduit ici. Seuls `dataset/input` et `dataset/metadata` ont été extraits, sans remplacer d’original existant. L’archive et les sorties restent ignorées par Git.

| Cas | Pages | Pages avec texte natif exploitable au catalogue |
|---|---:|---:|
| DOC-001 | 2 | 0 |
| DOC-002 | 2 | 0 |
| DOC-003 | 1 | 0 |
| DOC-004 | 2 | 0 |
| DOC-005 | 2 | 0 |
| DOC-006 | 1 | 0 |
| DOC-007 | 16 | 0 |
| DOC-008 | 5 | 0 |
| **Total** | **31** | **0** |

Le catalogue privé `dataset/metadata/prompt1-catalog.json` conserve nom, SHA-256, format, taille, pagination, métadonnées et version. Le présent rapport omet volontairement noms de fichiers d’origine, empreintes documentaires, extraits OCR, noms de personnes et autres identifiants. Les détections de langue/type issues de l’OCR sont heuristiques, pas des labels humains approuvés.

## Arborescence et preuves

- `dataset/input/` : originaux immuables ; contrôles SHA avant/après traitement.
- `dataset/metadata/` : catalogue et métadonnées privées existantes, plus catalogue vérifié de cette exécution.
- `dataset/preprocessing/` (dont final/) : par document/page, original rasterisé, variantes, selected, IR et previews.
- `dataset/ocr/` : espace privé réservé aux transcriptions et évaluations.
- `dataset/expected/` et `dataset/golden/` : **aucune référence humaine approuvée disponible**.
- `dataset/regression/` : dégradations contrôlées et variantes locales.
- `dataset/reports/` et `test-report/prompt-1/` : artefacts privés, traces et XML techniques.
- `reports/prompt-1/` : rapports publics techniques nettoyés.

Chaque original est paramétré dans `backend/tests/golden_dataset/test_golden_dataset.py`. Cette exécution a passé les huit cas (8 passed) sur le pipeline réel local, y compris OCR et reconstruction offline. Leurs résultats techniques définitifs sont dans TEST-REPORT.md. Le mode offline n’est jamais présenté comme une traduction Qwen validée.

## Pourquoi aucun Golden Expected n’a été fabriqué

Les huit PDF sont des **Golden Inputs potentiels**, pas des traductions ou transcriptions attendues validées. Il n’existe ni traduction humaine approuvée, ni transcription source approuvée, ni rubrique de fidélité humaine, ni baseline privée associée au tenant Golden dans cette exécution.

En conséquence :

- CER/WER réels, exactitude noms/dates/nombres/références OCR : **null**.
- Traduction modèle des 8 originaux : **NOT_EXECUTED par décision utilisateur (confidentialité)** ; aucun texte/IR/OCR/image/métadonnée/SHA envoyé au proxy Interim/OpenAI.
- Interim live : fixtures synthétiques codées uniquement, jamais promues Golden humains ; voir INTERIM-TRANSITION.md.
- Qualité linguistique multilingue Qwen : **NOT_AVAILABLE_IN_ENVIRONMENT**.
- Qualification métier/country/style, signatures et cachets exhaustifs : **non validée**.
- Gate strict Golden/release : conservé fail-closed ; aucun PASS bancaire inventé.
- Un test technique réussi pour un document prouve son traitement local, **pas la validation de sa traduction**.

Les API de revue existantes permettent ultérieurement une promotion par humain avec attestation, SHA, version, tenant et rubrique. Elles n’ont pas été contournées. Les glossaires métier seed ne remplissent jamais `dataset/expected` et ne sont pas des références humaines.

## Non-régression et reproduction

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/golden_dataset -q \
  --junitxml=test-report/prompt-1/golden.xml
PYTHONPATH=backend .venv/bin/python tools/preprocessing_benchmark.py --degradations
```

La première commande exige les originaux locaux, ignorés par Git. La recette privée Qwen exige en plus endpoint allowlisté, tokenizer réel local, références humaines tenant-scopées et baseline. La CI publique de tests techniques ne reçoit **jamais** ce corpus privé. Le gate privé existant vérifie explicitement le provisioning et ne publie pas d’artefacts confidentiels.
