# Rapport des tests exécutés — prompt 2

**Branche :** `feature/prompt-2-fidelite-20261008`  
**Base commune :** `6fb913a3a402e45c5813bf343fb85f26ef0e0e20`  
**Environnement :** clone isolé local (chemin non publié), venv Python 3.12.3 propre au clone, node_modules propres au frontend. Tests locaux et artefacts privés uniquement.

## Résultat final, sans double comptage

| Périmètre | Tests uniques PASS | FAIL final | Preuve |
| --- | ---: | ---: | --- |
| Python techniques, unit/integration/E2E/regression/security | **226** | **0** | `test-report/prompt-2/delivery-technical.xml` et `.log` |
| Corpus réel, dernier résultat par document après reprises ciblées | **8** | **0** | `final-corpus-latest.xml` + `corpus-corrected.xml` |
| **Python total unique** | **234** | **0** | Union des identifiants testcase, dernières reprises prioritaires |
| Angular/Vitest, frontend inchangé | **12** | **0** | `final-angular-tests.log` ; 4 fichiers |
| **Total Python + Angular unique** | **246** | **0** | Pas d’addition des exécutions répétées |
| Ruff backend/tools | PASS | 0 | `final-ruff.log` |
| TypeScript typecheck | PASS | 0 | `final-angular-typecheck.log` |
| Angular production build | PASS | 0 | `final-angular-build.log` |
| `git diff --check` | PASS | 0 | Exécuté avant commit |

Les huit derniers PASS corpus sont une **consolidation honnête**, pas une prétendue commande monolithique ayant passé 234 tests. Le run corpus `final-corpus-latest.xml` a passé DOC-001/DOC-006 et échoué sur six autres ; ces six IDs ont tous été réexécutés après correction et ont passé dans `corpus-corrected.xml`. Le dernier run technique définitif a ensuite passé 226 tests. Les journaux d’échecs précédents restent conservés, non effacés.

### Corpus confidentiel

- **8 originaux PDF, 31 pages**, traités localement avec le moteur existant et Tesseract.
- **31 triplets `original.png` / `translated.png` / `diff.png`**, avec `metrics.json` et `result.json`, disponibles dans les répertoires privés correspondants. Le résumé privé `test-report/prompt-2/corpus-final-summary.json` localise chaque artefact.
- SHA256 des **8/8** originaux vérifié de nouveau après les tests : **aucune altération**.
- Tous les candidats : `REVIEW_REQUIRED`, `reference_status=not_evaluated`, traduction/sémantique **null** ; absence de Golden humain conservée.
- Aucune donnée RH, OCR, IR ou preview n’a été envoyée à un LLM/service externe ; aucun appel live Qwen/Interim de cette branche.
- Le résumé versionné `CORPUS_TECHNICAL_SUMMARY.json` contient seulement IDs abstraits, décomptes de pages et états techniques non identifiants. Aucun SHA personnel/filename source/texte documentaire n’y figure.

## Baseline et résultats intermédiaires conservés

| Exécution réelle | PASS | FAIL | Cause constatée et résolution |
| --- | ---: | ---: | --- |
| Baseline intacte avant disponibilité OCR complète | 166 | 9 | Tesseract/traineddata manquants et statut de référence incohérent ; dépendances locales installées, sans modèle neuronal public |
| Baseline intacte après disponibilité OCR | **167** | **8** | Huit échecs corpus : provider `not_available`, contrat test exige `not_evaluated` ou `validated` ; normalisation pipeline corrigée, tests historiques inchangés |
| Première intégration ciblée | 56 | 1 | IDs DOCX historiques renommés ; rétablis, test préexistant passé sans relâcher assertion |
| Première suite complète post-intégration | 219 | 1 | DOC-006 : graphique original débordant la page ; clip **détection automatique** à l’intersection visible avec provenance et warning. Annotations utilisateur hors page restent refusées |
| Run technique intermédiaire renforcé | 218 | 1 | Test nouveau attendait encore package APPLIED ; exigence **renforcée** REVIEW_REQUIRED multistyle + changed_blocks=1, pas suppression du cas |
| Corpus après clipping / relecture | 2 | 6 | Dessins remplis PyMuPDF `width=None` non gérés dans preuve table ; correction `float(width or 0)` et test de régression dédié |
| Réexécution des six seuls cas échoués | **6** | **0** | DOC-002/003/004/005/007/008, 429.34 secondes |
| Dernière suite technique complète | **226** | **0** | 121.61 secondes, sources finales |

Les premiers tests de modules nouveaux ont également servi au développement (frontières de redistribution, caractères/espaces, signature d’appel de budget). Ils ne sont pas comptés comme tests finaux additionnels ni cachés derrière une baseline fabriquée. Aucune assertion historique n’a été supprimée ou relâchée.

## Couverture ajoutée et exercée

Les **59 nouveaux tests techniques** complètent les 167 préexistants.

| Domaine | Cas effectivement testés |
| --- | --- |
| DOCX runs/styles | gras/italique/souligné/taille/couleur/highlight, paragraph properties/numbering, redistribution traçable multi-run, espaces, semantic_alignment=false et REVIEW_REQUIRED |
| OOXML protégé | hyperlinks/bookmarks/fields, tabs/breaks, résultats de champs complexes traversant paragraphes, DrawingML non-Word non modifié, textbox imbriquée refusée |
| Package/refs | media/custom parts intacts, modifications XML hors texte détectées, refs numériques/negative invalides, header/footer/notes et wrappers Word, original SHA, symlink/hardlink/source-out alias |
| Tables DOCX | gridSpan/vMerge/rowSpan, width/height/borders/shading/header row, cellules vides, plusieurs paragraphes, nested tables et source_ref stable |
| PDF cellules | fusions rectangulaires, fill/borders/padding/align, texte cible dans la vraie cellule candidate, preflight overflow conservant la source, rollback final forcé |
| PDF adversarial | table supprimée/fill altéré/texte cible absent, visuel vectoriel dans cellule protégé, width=None des dessins remplis |
| Fidélité globale | bloc source inchangé disparu critique, mauvaise page, sous-mot faux positif refusé, plages disjointes sans double utilisation des glyphes, vrais pixels protégés |
| Masques/preuve | dimensions propres aux pages, mask trop large ne donne pas PASS, bbox protégée hors page measured=false, rendu manquant NOT_AVAILABLE_IN_ENVIRONMENT, artefacts réels |
| Pagination réelle | LibreOffice source/candidat, augmentation de pages en revue, source/candidat PDF réouverts |
| Contexte 32K | fixtures 10K/20K/22K/25K/30K/31K/32K/32K+, budget total et refus du transport oversize, tokenizer de comptage explicitement synthétique |
| Non-régression | API uploads/jobs/review, frontières tenant/auth/audit/storage, migrations, Celery, memory/glossary, transport privé, scénarios E2E, Angular reviewer |

Les unit tests transport existants emploient des doubles de contrat là où c’est pertinent ; **aucun double ne constitue une preuve live Qwen**. Les tests 32K nouveaux ne prétendent pas reproduire la tokenisation exacte du modèle privé indisponible.

## Mesures renderer avant/après

`tools/prompt2_fidelity_measure.py` charge réellement la base par `git show`, puis reconstruit les mêmes fixtures synthétiques sur le moteur intégré. Valeurs, cibles, rendus et provenance sont détaillés dans `DOCUMENT_FIDELITY_REPORT.md` et `SYNTHETIC_MEASUREMENTS.json`.

Les runs non vides passent de **1 à 3**, sans modifier les trois runs/propriétés du package. Les invariants graphiques de la table PDF passent de **0 à 1**, avec quatre textes cibles vus dans leurs vraies cellules et aucun overflow. Les scores layout/raster sont issus du rendu, pas recopiés de l’IR ; le style sémantique et GLOBAL restent inconnus. Les rendus DOCX/PDF synthétiques ont été inspectés visuellement ; ce n’est pas une approbation humaine linguistique.

## Gates et composants indisponibles

| Gate / composant | Exécution / résultat | Interprétation |
| --- | --- | --- |
| `tools/verify_acceptance.py --root .` | **FAIL attendu**, exit 1 | Golden humains, métriques IA/calibration et providers privés absents ; pas certification bancaire |
| `tools/compare_baseline.py` sans baseline humaine approuvée | **NOT_EVALUATED**, exit 2 | Aucune baseline qualité inventée |
| Qwen endpoint/poids/tokenizer exact privés | **NOT_AVAILABLE_IN_ENVIRONMENT** | Adapter existant seulement ; aucune exécution live revendiquée |
| CER/WER traductif/semantic embeddings/judge | **NOT_AVAILABLE_IN_ENVIRONMENT** sans preuves | null ≠ PASS |
| Attribution sémantique des styles | **non validée** | multistyles et champs/frontières ambigus restent en revue |
| Authenticité signatures/cachets/logos/QR | **non vérifiée** | conservation visuelle d’original, jamais génération/authentification |
| Calibration bancaire / revue humaine Golden | **non validée** | exécution terminée ≠ recette/banque approuvée |
| Preprocessing/API UI P1 | Interfaces consultées en lecture seule | merge final du coordinateur, pas de rebase/cherry-pick/merge P2 |

Le provider temporaire Interim annoncé par le coordinateur est réservé aux **synthétiques de P1**, pas au corpus RH. P2 reste local, sans appel LLM.

## Avertissements et reproductibilité

Les runs réussis conservent les warnings externes Starlette/httpx, Pillow `getdata`, alias PyMuPDF `fitz`, Alembic path separator ; le build Angular signale des optional chains inutiles. Ils n’ont pas été supprimés artificiellement. Les scopes de pytest, JUnit, logs, corpus et dépendances sont tous isolés de l’autre exécution ; aucun service/port/volume partagé n’a été reconfiguré.

```bash
# Suite technique finale (234 Python uniques inclut les 8 corpus séparés)
PYTHONPATH=backend .venv/bin/pytest backend/tests/unit backend/tests/integration \
  backend/tests/e2e backend/tests/regression backend/tests/security
# Corpus : implique OCR réel local et peut durer plusieurs minutes
PYTHONPATH=backend .venv/bin/pytest backend/tests/golden_dataset/test_golden_dataset.py
.venv/bin/ruff check backend tools
(cd frontend && npm run typecheck && npm test && npm run build)
```

Les logs bruts et artefacts contenant du contenu documentaire restent sous `test-report/prompt-2/`, exclu de Git. Le fichier `EXECUTION-RESULT.json` est le signal final de coordination.
