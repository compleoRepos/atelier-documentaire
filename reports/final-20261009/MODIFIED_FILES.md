# Fichiers modifiés — industrialisation finale (09/10)

Branche : `feature/industrialisation-finale-20261009`, créée depuis `60bd172`.
Chaque défaut `Dn` est décrit dans `AUDIT_CORRECTIFS.md`. Les volumes indiqués sont ceux de `git diff --numstat` (lignes ajoutées / supprimées) ou de `wc -l` pour un fichier nouveau.

## Code applicatif modifié

| Fichier | + / − | Défauts | Fonctions principales |
|---|---|---|---|
| `backend/app/ai/context/builder.py` | 25 / 1 | D10 | `_unit_wire`, `ContextPackBuilder.build_chunks` |
| `backend/app/ai/ocr/tesseract.py` | 120 / 15 | D7, D14, D15 | reprise de timeout bornée, `split_line_at_gaps` (découpage aux grands blancs, isolement des glyphes hauts) |
| `backend/app/ai/translation/service.py` | 191 / 7 | D8, D9, D11, D12, D21, D25, D26, D27 | reprise unique des sorties inchangées, hors blocs rejetés par la garde d’entités ; sortie typographique ramenée à la source ; exclusion des blocs OCR peu fiables, en désaccord de lecture, à risque de structure, d’identifiants seuls et d’écriture minoritaire, avec issues de revue |
| `backend/app/documents/docx_fidelity.py` | 22 / 3 | D17 | paragraphe constitué d’un unique hyperlien |
| `backend/app/documents/pdf_fidelity.py` | 896 / 53 | D2, D3, D11, D13, D16, D20, D22, D24 | plan de rendu scan (`_plan_scan_block`, `_scan_covers`, `_scan_font_size`), repli mono-ligne vérifié, garde d’encre source (`_drop_text_over_source_ink`, `_uncovered_source_ink`), masques étendus, obstacles d’encre et contrôle des bandes de croissance |
| `backend/app/documents/pipeline.py` | 375 / 90 | D1, D2, D11, D27 | appel de la segmentation, des indices de style et de `verify_lines` ; `UNTRANSLATED` sur variante typographique (`evaluate_document`) |
| `backend/app/documents/protected_visuals.py` | 268 / 4 | D4, D5, D6 | reclassification traçable, veto multicolore, chevauchement significatif sur scans, trace idempotente (`_merge_trace`) |
| `tools/interim_owner_corpus_run.py` | 8 / 0 | D19 | réapplication de `verify_lines` en réutilisation d’analyse |

> **Note sur `pipeline.py`.** Le fichier de `60bd172` ne respectait pas `ruff format`. Un `ruff format` appliqué pendant les correctifs l’a reformaté en entier : le volume brut (375 / 90) est donc surtout du formatage. La CI n’exécute que `ruff check backend tools`, sans contrôle de format. Le fichier reformaté est conservé, car c’est exactement le code exécuté par le passage final et par les tests (empreinte `f69a6210b29e8196`). Pour isoler les changements réels, comparer le fichier de la branche à la version de `60bd172` passée par `ruff format` (configuration du dépôt) : il reste 91 lignes de différence.
> ```
> git show 60bd172:backend/app/documents/pipeline.py | ruff format --stdin-filename backend/app/documents/pipeline.py - > /tmp/pipeline_60bd172_fmt.py
> diff -u /tmp/pipeline_60bd172_fmt.py backend/app/documents/pipeline.py
> ```

## Code applicatif ajouté

| Fichier | Lignes | Défauts | Rôle |
|---|---|---|---|
| `backend/app/documents/segmentation.py` | 849 | D1, D2, D9, D25 | regroupement sémantique des lignes OCR, indices de style, `is_unreliable_ocr` |
| `backend/app/documents/line_verification.py` | 434 | D6, D11, D12, D21, D23, D25 | surlignage, double lecture sous surligneur, garde de structure formulaire, identifiants seuls, écriture minoritaire, recalcul du drapeau OCR peu fiable |
| `backend/app/ai/translation/typography.py` | 42 | D27 | équivalence typographique (`typography_key`, `typography_equivalent`) partagée par le service, le pipeline et l’outil de mesure |

## Outils de recette ajoutés (sans données)

Les deux outils refusent d’écrire dans le dépôt.

| Fichier | Lignes | Rôle |
|---|---|---|
| `tools/recette/measure_corpus_metrics.py` | 578 | métriques par document : couvertures stricte, texte et écrite ; raisons de non-traduction ; résiduel OCR ; zones visuelles en union ; anomalies dédoublonnées ; même règle d’équivalence typographique que l’application (D27) |
| `tools/recette/compare_visual_sheets.py` | 143 | planches original / avant / après / différences, audit des zones visuelles |

## Tests ajoutés

Tous synthétiques. Les fragments réels copiés pendant le débogage ont été remplacés avant le commit (voir `TEST_REPORT.md` §3, audit de confidentialité).

| Fichier | Lignes | Défauts couverts |
|---|---|---|
| `backend/tests/unit/test_context_wire_budget.py` | 62 | D10 |
| `backend/tests/unit/test_cover_growth_final.py` | 185 | D22, D23, D24 |
| `backend/tests/unit/test_docx_final_audit_hyperlink.py` | 62 | D17 |
| `backend/tests/unit/test_docx_final_audit_invariants.py` | 264 | invariants DOCX (audit) |
| `backend/tests/unit/test_final_regression_gaps.py` | 133 | catégories §16 sans test dédié (texte résiduel PDF natif, faible contraste) |
| `backend/tests/unit/test_form_structure_guard_final.py` | 250 | D6, D12, D13 |
| `backend/tests/unit/test_inflated_line_box_final.py` | 135 | D15, D16 |
| `backend/tests/unit/test_line_verification_final.py` | 212 | D11 |
| `backend/tests/unit/test_interim_unchanged_retry.py` | 141 | D8, D26 |
| `backend/tests/unit/test_ocr_line_gap_split.py` | 85 | D14 |
| `backend/tests/unit/test_ocr_no_confidence_final.py` | 68 | D25 |
| `backend/tests/unit/test_protected_visuals_final.py` | 220 | D4, D5, D6 |
| `backend/tests/unit/test_scan_render_plan_final.py` | 149 | D3 |
| `backend/tests/unit/test_segmentation_final.py` | 256 | D1, D2, D9 |
| `backend/tests/unit/test_source_ink_guard_final.py` | 187 | D20, D21 |
| `backend/tests/unit/test_typography_only_output_final.py` | 109 | D27 |
| `backend/tests/unit/test_tesseract_timeout_retry.py` | 65 | D7 |

## Rapports (ce répertoire)

`AUDIT_CORRECTIFS.md`, `TEST_REPORT.md`, `DOCUMENT_FIDELITY_REPORT.md`, `TRANSLATION_COVERAGE_REPORT.md`, `CORPUS_METRICS_FINAL.json` (compteurs anonymisés uniquement), `REPRODUCTION.md`, `MODIFIED_FILES.md`, `EXECUTION-RESULT.json`.

## Non modifié

- Frontend Angular : aucun fichier modifié. Il a été contrôlé : typecheck, tests, build et audit npm.
- Schéma de base de données et migrations Alembic.
- Docker, Compose, Helm.
- Clients des fournisseurs : Interim (`interim.py`, `interim_guard.py`) et Qwen.
