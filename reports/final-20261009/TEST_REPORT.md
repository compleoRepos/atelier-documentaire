# Rapport de tests — industrialisation finale (09/10)

## 1. Version testée

- **Branche** : `feature/industrialisation-finale-20261009`, créée depuis `60bd172`.
- **Empreinte du code exécuté** : `f69a6210b29e8196`. C’est le SHA-256 tronqué de la concaténation triée des `sha256sum` de tous les fichiers `*.py` de `backend/app` et `tools`, hors `__pycache__` (commande dans `REPRODUCTION.md` §1).
  - Le corpus golden et le passage corpus Interim run17 ont tourné sur cette empreinte.
- **Empreinte du code committé** : `f2d0950f03f0d780`.
  - Différence avec l’empreinte exécutée : **uniquement la docstring d’en-tête** de `backend/app/documents/line_verification.py`. L’audit de confidentialité (§3) y a retiré deux valeurs réelles citées en exemple.
  - L’arbre syntaxique (AST) du module, docstrings exclues, est **identique** à celui de la version exécutée. Le comportement est donc inchangé.
  - La suite technique complète a été rejouée sur l’état committé (ligne « Technique backend » ci-dessous).
- **Environnement** :
  - Python 3.12.3, pytest 9.1.1, ruff 0.16.10.
  - PyMuPDF 1.28.2, Pillow 12.3.0, NumPy 2.5.3.
  - Tesseract 5.3.4 (langues ara, deu, eng, fra, ita, nld, osd, spa), LibreOffice 24.2.7.2.
  - Node 22.13.0.
  - `OMP_THREAD_LIMIT=1` pour les traitements OCR.

## 2. Synthèse

| Suite | Commande | Exécutés | Réussis | Échoués | Ignorés | Durée |
|---|---|---|---|---|---|---|
| Technique backend (unit, integration, regression, security, e2e) | `pytest -q -p no:cacheprovider backend/tests --ignore=backend/tests/golden_dataset` (état committé) | 549 | 549 | 0 | 0 | 206 s |
| Corpus golden (8 originaux, moteur hors ligne) | `pytest -v -p no:cacheprovider backend/tests/golden_dataset` | 8 | 8 | 0 | 0 | 1 157 s |
| Frontend Angular : tests | `npm test` | 16 (6 fichiers) | 16 | 0 | 0 | — |
| Frontend Angular : typecheck, build | `npm run typecheck`, `npm run build` | — | OK (rc=0) | — | — | — |
| Audit npm | `npm audit` | — | 0 vulnérabilité | — | — | — |
| Lint (règle de la CI) | `ruff check backend tools` | — | OK | — | — | — |
| Formatage (non imposé par la CI) | `ruff format --check` sur les fichiers modifiés/ajoutés | 30 | 29 | 1 | — | — |
| Espaces / fins de ligne | `git diff --check` | — | OK | — | — | — |

Répartition des 549 tests techniques : unit 513, integration 28, e2e 3, security 3, regression 2.

**Aucune régression.** Évolution de la suite technique au fil des correctifs, toujours avec 0 échec : 438 (run3), 504, 534, 539, puis **549**. L’ajout de tests n’a modifié aucune attente d’un test existant.

Suites interrompues volontairement : plusieurs suites ou corpus golden lancés en cours de mission ont été arrêtés parce que le code changeait (nouveau correctif). Ces exécutions sont **ignorées**, aucune n’est comptée ici. Seules les exécutions sur l’empreinte finale figurent dans ce rapport.

Formatage : le seul fichier non conforme à `ruff format` est `tools/interim_owner_corpus_run.py`. Il l’était **déjà** dans `60bd172`. Le diff de cette mission n’y ajoute que 8 lignes, et le fichier n’a pas été reformaté pour garder un diff minimal. La CI n’impose que `ruff check`, qui passe.

## 3. Tests ajoutés (131 tests, 17 fichiers, tous synthétiques)

Les rasters, PDF et textes sont générés dans le code des tests.

**Audit de confidentialité avant commit.** Plusieurs tests avaient été écrits en reproduisant des cas mesurés sur le corpus. Un contrôle systématique a donc été fait avant commit : chaque chaîne littérale des fichiers ajoutés ou modifiés (n-grammes de 3 mots, nombres d’au moins 6 chiffres, mots capitalisés) a été comparée au texte OCR des 8 analyses réelles.

- **Fragments réels trouvés** dans 7 fichiers de tests et dans une docstring du code :
  - noms et prénoms de personnes ;
  - phrase d’attestation avec date d’embauche ;
  - numéros de téléphone et de fax ;
  - un numéro de compte bancaire et un identifiant d’entreprise ;
  - dates, ville et pays, nom d’organisation.
- **Correction** : tous ont été remplacés par des valeurs synthétiques de même forme et de même longueur, et les tests concernés ont été rejoués.
- **Historique** : la recherche `git log --all -S` confirme qu’**aucun** de ces fragments n’avait été committé ni poussé.
- **Ce qui reste** : uniquement du vocabulaire générique de formulaire (« Contrat de travail »… ; autres exemples expurgés en RUN28), sans donnée personnelle.

| Fichier | Tests | Défauts couverts (`AUDIT_CORRECTIFS.md`) |
|---|---|---|
| `backend/tests/unit/test_context_wire_budget.py` | 2 | D10 |
| `backend/tests/unit/test_cover_growth_final.py` | 10 | D22, D23, D24 |
| `backend/tests/unit/test_docx_final_audit_hyperlink.py` | 1 | D17 |
| `backend/tests/unit/test_docx_final_audit_invariants.py` | 4 | invariants DOCX |
| `backend/tests/unit/test_final_regression_gaps.py` | 5 | §16 : texte résiduel, faible contraste, double lecture réelle |
| `backend/tests/unit/test_form_structure_guard_final.py` | 25 | D6, D12, D13 |
| `backend/tests/unit/test_inflated_line_box_final.py` | 6 | D15, D16 |
| `backend/tests/unit/test_line_verification_final.py` | 17 | D11 |
| `backend/tests/unit/test_interim_unchanged_retry.py` | 4 | D8, D26 |
| `backend/tests/unit/test_ocr_line_gap_split.py` | 5 | D14 |
| `backend/tests/unit/test_ocr_no_confidence_final.py` | 4 | D25 |
| `backend/tests/unit/test_protected_visuals_final.py` | 10 | D4, D5, D6 |
| `backend/tests/unit/test_scan_render_plan_final.py` | 6 | D3 |
| `backend/tests/unit/test_segmentation_final.py` | 10 | D1, D2, D9 |
| `backend/tests/unit/test_source_ink_guard_final.py` | 9 | D20, D21 |
| `backend/tests/unit/test_tesseract_timeout_retry.py` | 3 | D7 |
| `backend/tests/unit/test_typography_only_output_final.py` | 10 | D27 |

Ces comptes sont ceux du JUnit final (tests paramétrés comptés par cas).

## 4. Correspondance avec les catégories exigées (§16)

Chaque catégorie est couverte par au moins un test ciblé, exécuté et réussi dans la suite finale. Les chemins sont relatifs à `backend/tests/`.

| Catégorie | Tests ajoutés | Tests existants conservés |
|---|---|---|
| Paragraphes de plusieurs lignes OCR | `unit/test_segmentation_final.py::test_multiline_paragraph_is_one_block_with_traceable_lines`, `::test_segment_ir_remaps_table_references_to_the_group_id` ; `unit/test_scan_render_plan_final.py::test_grouped_paragraph_gets_one_cover_per_source_line_and_one_text_box` | — |
| Titres courts | `unit/test_segmentation_final.py::test_short_title_stays_separate_from_following_paragraph` ; `unit/test_inflated_line_box_final.py::test_one_line_heading_in_a_tall_box_is_not_wrapped_onto_the_next_row`, `::test_one_line_heading_without_room_reports_overflow_instead_of_wrapping` ; `unit/test_scan_render_plan_final.py::test_body_lines_share_one_size_and_headings_keep_theirs` | — |
| Texte gras | `unit/test_segmentation_final.py::test_bold_line_is_detected_from_raster_stroke_evidence` ; `unit/test_scan_render_plan_final.py::test_measured_bold_and_highlight_are_applied` | — |
| Texte sous surlignage | `unit/test_segmentation_final.py::test_highlighted_line_keeps_highlight_and_ink_evidence` ; `unit/test_line_verification_final.py::test_highlight_measured_on_saturated_light_pixels_not_paper`, `::test_partial_highlight_is_reported_as_partial`, `::test_renderer_fills_highlighted_line_with_measured_colour_only` ; `unit/test_final_regression_gaps.py::test_real_second_reading_under_highlight` ; `unit/test_protected_visuals_final.py::test_single_hue_highlight_is_not_a_logo` | `unit/test_preprocessing_speckle_filter.py::test_real_stamp_and_highlight_are_still_candidates` |
| Tableaux denses | `unit/test_form_structure_guard_final.py::test_vertical_rule_crossing_a_line_is_detected_but_glyph_strokes_are_not`, `::test_horizontal_rule_between_two_lines_is_detected`, `::test_structural_and_identifier_blocks_are_never_sent_nor_rewritten` ; `unit/test_segmentation_final.py::test_lines_in_different_table_cells_are_never_merged`, `::test_side_by_side_columns_are_not_merged` | `unit/test_raster_rectangles_merge.py::test_dense_ruled_page_is_bounded_in_time_and_reports_saturation` |
| Cellules fusionnées | `unit/test_cover_growth_final.py::test_cell_separator_leaving_the_line_on_one_side_is_a_rule`, `::test_rule_crossing_on_both_sides_is_still_detected` | `unit/test_scan_layout_v2.py::test_vector_2x3_grid_links_existing_blocks_and_preserves_merged_cell` |
| Cases à cocher | `unit/test_form_structure_guard_final.py::test_ruling_glyphs_only_at_structural_positions` (cases à chiffres) | `unit/test_scan_layout_v2.py::test_raster_checkbox_is_candidate_with_human_state_uncertainty`, `::test_large_raster_pseudotext_is_bounded_and_keeps_table_and_checkbox` |
| Cachets et signatures | `unit/test_scan_render_plan_final.py::test_stamp_touching_the_corner_is_avoided_not_overwritten`, `::test_stamp_covering_the_text_blocks_the_replacement` ; `unit/test_protected_visuals_final.py::test_corner_contact_is_not_significant_but_real_cover_is`, `::test_human_annotation_contact_still_protects`, `::test_multicolour_pictogram_inside_an_ocr_line_stays_protected`, `::test_human_and_native_regions_are_never_reclassified` ; `unit/test_segmentation_final.py::test_signature_lines_keep_their_deliberate_line_break`, `::test_protected_line_is_never_merged` | `unit/test_preprocessing_prompt1.py::test_crop_keeps_text_and_edge_protected_signature` ; `unit/test_preprocessing_speckle_filter.py::test_real_stamp_and_highlight_are_still_candidates` |
| Texte chevauchant un élément graphique | `unit/test_source_ink_guard_final.py::test_text_over_unmasked_source_ink_is_dropped_with_critical_issue`, `::test_table_rule_through_the_line_is_structure_not_residual_text` ; `unit/test_cover_growth_final.py::test_rule_touching_the_box_is_an_obstacle_never_absorbed`, `::test_horizontal_rule_above_the_box_stops_and_rejects_upward_growth` ; `unit/test_inflated_line_box_final.py::test_tall_graphic_word_is_isolated_from_the_line_it_inflates`, `::test_ink_under_a_one_line_block_forbids_the_wrap_fallback` ; `unit/test_protected_visuals_final.py::test_coloured_title_letters_are_text_but_a_logo_beside_them_is_kept` | `unit/test_audit_guards_prompt2.py::test_vector_graphic_inside_table_cell_blocks_replacement_and_preserves_pixels` ; `unit/test_pdf_cell_fallback.py::test_page_frame_cell_touching_logo_falls_back_to_unprotected_blocks` |
| Documents inclinés | — (aucune correction de redressement dans cette phase) | `unit/test_preprocessing_prompt1.py::test_rotation_expands_canvas_and_has_exact_inverse`, `::test_perspective_four_corners_when_safe` ; `unit/test_prompt1_ingestion.py::test_real_orientation_and_deskew_probes_do_not_claim_validated_cer` |
| Faible contraste | `unit/test_final_regression_gaps.py::test_low_contrast_scan_gets_contrast_variant_and_keeps_values` | `unit/test_preprocessing_prompt1.py::test_photometric_methods_are_copies_and_bounded` |
| Texte résiduel | `unit/test_final_regression_gaps.py::test_residual_source_text_is_detected_when_translation_is_not_rendered`, `::test_rendered_translation_leaves_no_source_text` ; `unit/test_source_ink_guard_final.py::test_masked_source_ink_does_not_block_the_replacement` ; `unit/test_cover_growth_final.py::test_extended_cover_recovers_a_block_whose_own_source_was_left_unmasked` | `unit/test_documents_pipeline.py::test_native_pdf_ignores_whitespace_residue_and_preserves_original` |
| Débordement et coupure | `unit/test_scan_render_plan_final.py::test_overflow_is_reported_and_source_kept_instead_of_truncating` ; `unit/test_inflated_line_box_final.py::test_one_line_block_may_wrap_only_into_space_proven_blank` | `unit/test_documents_pipeline.py::test_overflow_is_blocking` ; `unit/test_pdf_cell_fallback.py::test_overflowing_scan_cell_falls_back_to_blocks` ; `unit/test_pdf_fidelity_prompt2.py::test_overflow_is_atomic_and_source_text_is_restored` |
| Données critiques modifiées | `unit/test_interim_unchanged_retry.py::test_entity_guard_rejection_is_not_retried_as_unchanged` ; `unit/test_line_verification_final.py::test_disagreeing_second_reading_marks_block_and_keeps_counts_only`, `::test_disagreeing_block_is_never_sent_nor_rewritten`, `::test_digit_sequence_ignores_spacing_and_single_digits` ; `unit/test_typography_only_output_final.py` (un chiffre modifié n’est jamais une variante typographique) | `unit/test_entities_multilingual.py::test_changed_iban_digit_is_critical`, `::test_changed_localised_date_is_still_critical` ; `unit/test_translation.py::test_dates_iban_mail_phone_numbers_and_protected_name_are_restored_exactly` |

## 5. Rejeu du corpus des huit PDF

Le corpus est rejoué de deux façons complémentaires, toutes deux sur l’empreinte finale.

1. **Corpus golden** (`backend/tests/golden_dataset`). Il traite les 8 originaux avec le moteur hors ligne, sans réseau. Pour chaque document, il vérifie :
   - le nombre et la numérotation des pages de l’IR ;
   - la production du candidat ;
   - le statut `REVIEW_REQUIRED` ;
   - `translation_score` à `NULL` ;
   - un statut de référence « non évalué » ou « indisponible » tant qu’aucune référence humaine n’est validée.

   Il garantit ainsi l’absence de PASS artificiel. Le contrôle des SHA des originaux est assuré par le lanceur du passage Interim (point 2). Résultat : **8/8 PASSED en 1 156,7 s**, sur l’empreinte exécutée `f69a6210b29e8196`, de comportement identique au code committé.
2. **Passage corpus Interim réel run17**, autorisé par le propriétaire et limité aux 8 SHA admis.
   - 8/8 documents traités, `error=null` partout, SHA originaux inchangés.
   - **63 requêtes** au total. Maximum réservé par requête : 20 988 tokens, pour une borne de 32 768. Maximum consommé : 2 498.
   - **0 violation de budget**, 0 requête au-delà de 32 768, que ce soit en réservé ou en usage réel.
   - Statut : 8/8 `REVIEW_REQUIRED`.
   - Résultats détaillés dans `DOCUMENT_FIDELITY_REPORT.md` et `TRANSLATION_COVERAGE_REPORT.md`.

## 6. Non exécuté (statut explicite, jamais converti en PASS)

| Élément | Statut | Raison |
|---|---|---|
| Traduction par Qwen privé | NOT_AVAILABLE | Endpoint, tokenizer et poids privés non fournis. Le budget 32K et l’interface fournisseur sont testés avec des doubles. |
| CER / WER OCR, scores de traduction | NOT_AVAILABLE (`NULL`) | Aucune transcription ni traduction de référence validée par un humain. |
| Validation humaine des 8 documents | NON EXÉCUTÉE | Hors périmètre automatisé. Elle justifie le statut `REVIEW_REQUIRED`. |
| Portes d’acceptation privées de la CI | SKIPPED en CI | Les originaux ne sont jamais déposés sur GitHub. Ces portes sont exécutées localement (§5). |
| Build Docker / Compose / Helm local | Non rejoué localement | Aucun fichier d’infrastructure modifié. Le build est couvert par les jobs de la CI. |

## 7. Reproduire

Toutes les commandes, variables et chemins privés attendus sont décrits dans `REPRODUCTION.md`.

## 8. Intégration continue (SHA exact du code)

- **Source testée** : `ebb09ebc54122aa25677157ed55d43edf4f04fcc` (empreinte `f2d0950f03f0d780`).
- **Exécution** : [run 37882871159](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/37882871159), déclenchée par la PR brouillon #1 vers `main`, non fusionnée. Conclusion : **success**.

| Job | Résultat |
|---|---|
| `backend` | success |
| `backend-integration-and-migrations` | success |
| `frontend` | success |
| `container-and-manifest-validation` | success |
| `private-acceptance` | skipped (runner privé autorisé requis) |
| `manual-release-gate` | skipped (déclenchement manuel uniquement, fail-closed sans preuves privées) |

Les commits postérieurs à `ebb09eb` sur cette branche ne modifient que `reports/`.
