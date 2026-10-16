# RUN18 — Fichiers source modifiés

Base : `f44ebb8` (rapports seuls après `ebb09eb`). Aucun fichier de données, de corpus, d'analyse, de rendu ni
d'autorisation n'est versionné ; les sorties des passages restent dans un répertoire privé hors dépôt.

## Code applicatif (`backend/app`)

| Fichier | État | Correctifs | Fonctions principales |
|---|---|---|---|
| `ai/ocr/tesseract.py` | modifié | F1, F2b | `split_line_at_gaps` (mots hauts plafonnés au lieu d'isolés), `vertical_rule_between` (découpe aux filets verticaux) |
| `documents/line_verification.py` | modifié (version `line-verification-7`) | F2, F4 (appel), F9, F10, F11, F13, F13b, F17, F18 | `split_block_at_rules`, `checkbox_glyphs`, `_isolated`, `_declare_checkbox_regions`, `split_block_at_enumerators`, `normalize_mirrored_brackets`, `split_block_at_checkboxes`, `strip_checkbox_tokens`, `mixed_script_noise`, `verify_lines` |
| `documents/language_evidence.py` | **nouveau** | F4 | `refine_language`, `has_linguistic_content`, `identical_in_french`, `foreign_word_evidence` (wordfreq hors ligne, désactivé proprement si absent) |
| `documents/block_status.py` | **nouveau** | F7 | `classify_blocks` : un statut §10 et une raison par bloc |
| `documents/pdf_fidelity.py` | modifié | F5, F9, F12, F19 | `_plan_scan_block`, `_grow_left`, `_ink_obstacles`, `_growth_is_blank`, `_scan_style`, `_scan_region_protects`, `_fit_on_scratch` / `_longest_word_fits`, `_neighbour_obstacle` |
| `documents/protected_visuals.py` | modifié | F9 | région `checkbox_glyph` déclarée `carves_only` (découpe sans protéger tout le bloc) |
| `documents/pipeline.py` | modifié | F7, F15 | statuts par bloc dans la sortie, `_protected_for` cohérent avec le rendu pour les cases automatiques |
| `ai/translation/service.py` | modifié | F3 | `_retry_candidate` (reprise unique des sorties non latines ou étrangères inchangées) ; le contrôle de budget 32K est inchangé |

## Dépendances

| Fichier | Changement | Remarque |
|---|---|---|
| `backend/pyproject.toml`, `backend/requirements.txt` | `wordfreq==3.1.1` | données lexicales CC-BY-SA-4.0 : licence à valider avant distribution |

## Outils (`tools/`)

| Fichier | État | Rôle |
|---|---|---|
| `tools/interim_owner_corpus_run.py` | modifié | F16 : mémoire de traduction fermée par défaut (`--translation-cache`), signature de contenu, élagage des tableaux entièrement servis par la mémoire, conservation des vrais tableaux sans correspondance ; réutilisation d'analyse |
| `tools/recette/render_outcome.py` | **nouveau** | mesure indépendante du PDF rendu (WRITTEN / PARTIAL / ABSENT, texte sur encre résiduelle, collisions, hors page) ; M1 : zone symétrique |
| `tools/recette/measure_v2.py` | **nouveau** | métriques comparables `measure-v2.1-run18`, même méthode pour tous les passages ; écrit des compteurs uniquement, hors dépôt |
| `tools/recette/compare_runs_sheets.py` | **nouveau** | planches original / baseline / run17 / run18 + diffs, audit des régions visuelles ; destination hors dépôt imposée |

## Tests (`backend/tests/unit`)

| Fichier | État | Contenu |
|---|---|---|
| `test_run18_regressions.py` | **nouveau** | 39 tests synthétiques (F1–F19, mémoire de traduction) ; aucun contenu de corpus |
| `test_recette_render_outcome.py` | **nouveau** | 2 tests de la mesure indépendante (M1) |
| `test_form_structure_guard_final.py` | modifié | attentes D16 adaptées à la scission F2 (un bloc multi-rangées est scindé avant la garde) |
| `test_inflated_line_box_final.py` | modifié | attentes run10 adaptées à F1 (mot haut gardé dans sa ligne, hauteur plafonnée) |

## Rapports (`reports/run18-20261011`)

`README.md`, `RUN18_ROOT_CAUSE_ANALYSIS.md`, `RUN18_REGRESSION_REPORT.md`, `RUN18_DOCUMENT_FIDELITY_REPORT.md`,
`RUN18_TRANSLATION_COVERAGE_REPORT.md`, `MODIFIED_FILES.md`, `TEST_RESULTS.md`, `LIMITATIONS.md`,
`metrics/RUN18_METRICS_BY_DOCUMENT.json` (compteurs anonymisés).
