# AUDIT_CORRECTIFS — mission finale du 09/10/2026

Branche `feature/industrialisation-finale-20261009`, créée depuis `60bd172` (passage Interim autorisé des 8 originaux). Commit final : voir `EXECUTION-RESULT.json`.

**Règles de lecture.**

- Les documents sont désignés `DOC-001` à `DOC-008`. Aucun nom de fichier, SHA, texte, OCR, image ou chemin privé ne figure dans ce dépôt.
- Les chiffres « avant / après » sont des **compteurs mesurés**, jamais estimés :
  - outil `tools/recette/measure_corpus_metrics.py` ;
  - télémétrie Interim ;
  - journaux des passages successifs.
- Les passages corpus portent un numéro (`runN`).
  - Les passages 3 à 16 sont **intermédiaires**. Chacun a mis au jour un défaut, corrigé ensuite.
  - Le verdict final porte sur **run17** (empreinte du code exécuté `f69a6210b29e8196`, code committé `f2d0950f03f0d780` de même AST, voir `REPRODUCTION.md` §1). Ce passage réutilise l’OCR/IR frais de run10 (analyse complète sur le code final d’OCR), avec la vérification des lignes réappliquée, de nouvelles requêtes Interim et le rendu final. L’empreinte du code exécuté est consignée par le lanceur.
- La référence « avant » est la sortie précédente figée, **baseline-617**. Il s’agit de la livraison Interim du 08/10, `60bd172`.
- Aucun document n’est déclaré PASS. Les 8 restent `REVIEW_REQUIRED` : il n’existe pas de référence humaine validée, et des alertes critiques subsistent. Elles sont listées dans `DOCUMENT_FIDELITY_REPORT.md`.

## Synthèse des défauts

| # | Défaut | Gravité | Statut |
|---|---|---|---|
| D1 | OCR des scans segmenté ligne par ligne (pas de paragraphes) | Majeur | Corrigé |
| D2 | Style des scans perdu (gras, couleur, alignement) | Majeur | Corrigé (surlignage partiel : approximé, tracé) |
| D3 | Rendu scan : réduction excessive, masques imprécis, troncature silencieuse | Critique | Corrigé |
| D4 | Titres et libellés protégés à tort par des candidats visuels automatiques | Majeur | Corrigé |
| D5 | Logo multicolore lu comme une ligne OCR (risque d’effacement) | Critique | Corrigé |
| D6 | Cadres de formulaire reclassés : champs fusionnés, logos effacés | Critique | Corrigé (garde structure) |
| D7 | Timeouts Tesseract sous charge | Majeur | Corrigé |
| D8 | Interim renvoie parfois la source inchangée | Majeur | Corrigé (reprise bornée) |
| D9 | OCR illisible envoyé au LLM | Majeur | Corrigé |
| D10 | Faux `CONTEXT_OVERFLOW` (métadonnées de rendu comptées dans le budget 32K) | Critique | Corrigé |
| D11 | Surlignage perdu et date surlignée mal lue par l’OCR | Critique | Corrigé (double lecture sous surligneur) |
| D12 | Lignes d’identifiants seuls réécrites (dates, RIB/ICE, téléphones) | Critique | Corrigé |
| D13 | Police démesurée sur les lignes contaminées par un cachet | Majeur | Corrigé |
| D14 | Lignes OCR traversant des zones séparées | Critique | Corrigé |
| D15 | Boîte de ligne gonflée par un fragment graphique | Majeur | Corrigé |
| D16 | Titre d’une ligne replié sur la rangée de tableau suivante | Critique | Corrigé (règle mono-ligne + repli vérifié) |
| D17 | DOCX : paragraphe constitué d’un unique hyperlien jamais traduit | Mineur | Corrigé |
| D18 | Mesure de couverture gonflée, compteur `untranslated_blocks` non fiable | Majeur (mesure) | Corrigé (outil strict) |
| D19 | Réutilisation d’analyse sans réappliquer les vérifications | Majeur (recette) | Corrigé |
| D20 | Traduction dessinée par-dessus du texte source non masqué | Critique | Corrigé (garde d’encre, source conservée) |
| D21 | Bruit OCR d’écriture minoritaire envoyé au LLM | Majeur | Corrigé |
| D22 | Masques rétrécis devant des voisins eux-mêmes remplacés (source propre visible) | Majeur | Corrigé (masques étendus, dessin en deux phases) |
| D23 | Filet de cellule ne dépassant la ligne que d’un côté non détecté | Critique | Corrigé |
| D24 | Cadre de traduction agrandi dans de l’encre originale (filets, libellés) | Critique | Corrigé (débordement signalé à la place) |
| D25 | Fragment OCR de confiance nulle ressemblant à un mot, traduit et écrit | Majeur | Corrigé |
| D26 | Reprise « inchangé » (D8) contournant le rejet de la garde d’entités | Critique | Corrigé |
| D27 | Sortie identique à la source à la typographie près acceptée comme traduction, sans alerte | Majeur | Corrigé |

Les défauts restants et les limites figurent en fin de document. Ils sont aussi repris dans `DOCUMENT_FIDELITY_REPORT.md` §4.

---

## D1 — Segmentation OCR ligne par ligne

- **Symptôme initial.** Sur la baseline, 1 ligne OCR donne 1 bloc. Les paragraphes étaient donc traduits ligne à ligne, sans contexte. Les masques et la police étaient calculés par ligne, et les phrases étaient coupées en plein milieu (baseline : 1 041 blocs IR pour 1 041 lignes OCR).
- **Cause.** `backend/app/ai/ocr/tesseract.py::TesseractOCR.image_to_blocks` regroupe par `(block, par, line)` Tesseract. `backend/app/documents/pipeline.py::_analyze_image` recopie ces lignes sans aucun regroupement.
- **Correction.** Nouveau module `backend/app/documents/segmentation.py` :
  - `segment_page`, `segment_ir`, `_group_block`, `remap_block_ids` ;
  - regroupement en paragraphes, titres, puces et cellules, selon des seuils calibrés sur l’interligne et la hauteur ;
  - colonnes et cellules jamais fusionnées ;
  - `source_lines` traçables, avec `line_heights`, `line_pitch` et le rôle ;
  - remappage des références de tableaux.

  Appel dans `pipeline.analyze_document` après `protect_ir`.
- **Tests.** `backend/tests/unit/test_segmentation_final.py`, 10 tests, dont :
  - `test_multiline_paragraph_is_one_block_with_traceable_lines` ;
  - `test_short_title_stays_separate_from_following_paragraph` ;
  - `test_lines_in_different_table_cells_are_never_merged` ;
  - `test_side_by_side_columns_are_not_merged` ;
  - `test_signature_lines_keep_their_deliberate_line_break`.
- **Avant / après.** Blocs IR : 1 041 → 1 148 en run17, pour 1 415 lignes OCR (après le découpage D14). Le détail par document se trouve dans `DOCUMENT_FIDELITY_REPORT.md`, tableau A.

## D2 — Style des scans perdu

- **Symptôme initial.** Sur les scans, la traduction était toujours écrite en régulier noir, alignée à gauche : titres gras, couleurs et centrage perdus.
- **Cause.** `backend/app/documents/pdf_fidelity.py::render_pdf` fixait `style={}` et `align=0` en dur sur la voie scan.
- **Correction.**
  - `segmentation.line_style_evidence` mesure le style sur le raster original rendu à 4×, sans s’appuyer sur l’OCR : épaisseur de trait relative au corps estimé en gras, couleur d’encre, fond, alignement.
  - `pdf_fidelity._scan_style` applique ce style au rendu.
  - **Défaut trouvé par test :** le gras était sous-mesuré, car la taille était estimée avec une police régulière alors qu’un gras est environ 13 % plus large. Corrigé avec `width_font_size(bold=True)`, ratio tracé dans `style.bold_stroke_ratio`.
- **Tests.**
  - `test_segmentation_final.py::test_bold_line_is_detected_from_raster_stroke_evidence` ;
  - `test_scan_render_plan_final.py::test_measured_bold_and_highlight_are_applied`.
- **Avant / après.** Style appliqué : aucun → gras, couleur, fond et alignement mesurés par bloc. Le surlignage partiel d’une ligne est reproduit sur toute la ligne traduite, avec la trace `HIGHLIGHT_SPAN_APPROXIMATED` : la position des mots n’est pas transposable d’une langue à l’autre.

## D3 — Rendu scan : réduction excessive, masques imprécis, troncature silencieuse

- **Symptôme initial.** Polices réduites jusqu’à environ 32 % de la hauteur. Résidus de source autour des masques. Texte tronqué sans alerte (baseline : 6 débordements, 195 textes coupés ou manquants, 146 mots source résiduels lisibles).
- **Cause.**
  - `_fit_on_scratch` réduisait jusqu’à `h*0.32` ;
  - le masque correspondait exactement à la bbox OCR ;
  - `_scan_line_size` divisait la hauteur du bloc par le nombre de lignes du texte traduit.
- **Correction.** `pdf_fidelity._plan_scan_block`, `_scan_covers`, `_scan_font_size`, `_height_line_size`, `_line_boxes` :
  - un masque par ligne source, avec une marge bornée, rétréci loin des voisins et des zones protégées (`SCAN_REDACTION_SHRUNK`) ;
  - taille issue de `line_heights` et du pitch ;
  - réduction bornée à 72 % (`_SCAN_MIN_FONT_RATIO`), avec `FONT_REDUCED` (info) en dessous de 85 % ;
  - au-delà, `LAYOUT_OVERFLOW` **critique**, source conservée : jamais de troncature silencieuse.
- **Tests.** `backend/tests/unit/test_scan_render_plan_final.py`, 6 tests, dont :
  - `test_overflow_is_reported_and_source_kept_instead_of_truncating` ;
  - `test_grouped_paragraph_gets_one_cover_per_source_line_and_one_text_box` ;
  - `test_body_lines_share_one_size_and_headings_keep_theirs`.
- **Avant / après (baseline → run17).** Mots source résiduels relus par OCR sur le candidat : 146 → 171, sur 1 854 mots éligibles côté baseline et 1 833 côté final. **Cette hausse est réelle.** Elle provient des sources conservées volontairement et signalées par les gardes : structure D6/D23, encre D20, débordements, OCR peu fiable D9. Ce n’est pas une perte silencieuse : les caractères manquants silencieux restent à 0. Texte traduit non retrouvé dans le PDF candidat (`missing_block_count` = blocs traduits − blocs retrouvés) : 65 → 92 blocs. Sur ce total, les blocs écartés par une garde signalée (`LAYOUT_OVERFLOW`, `SCAN_TEXT_OVER_SOURCE_INK`) passent de 6 à 60, et le **solde non attribuable de 59 à 32**. Les trois codes `RENDER_*_MISSING` portent ce même compteur : la catégorie agrégée, 195 → 276, le compte donc trois fois. Débordements signalés : 6 → 35. Après D16, ces débordements sont des alertes volontaires, avec source conservée.

## D4 — Titres et libellés protégés à tort

- **Symptôme initial.** Exemples :
  - DOC-001 : titre non traduit, car couvert par 5 candidats visuels (composantes couleur des lettres) ;
  - DOC-007 : libellés gras lus par l’OCR (confiance 0,80 à 0,93) mais marqués `protected`.

  Baseline : 82 blocs de texte protégés non traduits.
- **Cause.**
  - Les candidats automatiques du prétraitement (contours sombres, composantes couleur) protégeaient tout bloc qui les touchait, même par un simple contact.
  - Les cadres de formulaire et les lettres colorées étaient pris pour des visuels.
- **Correction.** `backend/app/documents/protected_visuals.py` :
  - `reclassify_text_candidates` : cadre contenant au moins 2 lignes lisibles → `text_container_frame` ; glyphes colorés dans une ligne lisible → `colored_text_glyphs`. Trace `PROTECTED_CANDIDATE_RECLASSIFIED_TEXT`, idempotente (`_merge_trace`).
  - `significant_overlap` : sur les scans, un candidat automatique ne protège qu’avec au moins 30 % du bloc ou 50 % de la zone. Sinon, le bloc est noté `near_protected_regions`.
  - Les annotations humaines et les PDF natifs restent stricts (`is_user_region`).
- **Tests.** `backend/tests/unit/test_protected_visuals_final.py`, 10 tests, dont :
  - `test_corner_contact_is_not_significant_but_real_cover_is` ;
  - `test_human_annotation_contact_still_protects` ;
  - `test_native_pdf_page_stays_strict` ;
  - `test_human_and_native_regions_are_never_reclassified`.
- **Avant / après.** Texte protégé non traduit : 82 → 22 blocs. Le reliquat correspond à de vrais cachets, logos et signatures.

## D5 — Logo multicolore lu comme une ligne OCR

- **Symptôme (audit visuel run4, DOC-001).** Après D4, 4 candidats pictogramme et logotype, lus par l’OCR comme une ligne, ont été reclassés en texte. Le logo n’a été préservé que parce que le nom propre n’était pas traduit.
- **Cause.** La règle des glyphes colorés ne distinguait pas un titre d’une seule teinte d’un pictogramme multicolore.
- **Correction.** `protected_visuals.multicolor_evidence` : au moins 2 familles de teinte distantes de 60° ou plus déclenchent un veto, et la zone reste protégée. Le veto est tracé dans l’IR. Un surlignage (une seule famille de teinte) n’est pas un logo.
- **Tests.**
  - `test_protected_visuals_final.py::test_multicolour_pictogram_inside_an_ocr_line_stays_protected` ;
  - `::test_coloured_title_letters_are_text_but_a_logo_beside_them_is_kept` ;
  - `::test_single_hue_highlight_is_not_a_logo`.
- **Avant / après.** DOC-001 : logo reclassé texte (run4) → protégé (veto multicolore depuis run5, teintes mesurées [0°, 150°]).

## D6 — Cadres de formulaire reclassés : champs fusionnés, logos effacés

- **Symptôme (régression run6, planches d’audit).**
  - DOC-007 : champs de 3 cellules fusionnés en une ligne en grande police ; cases à chiffres lues comme un seul nombre (filets de case lus comme des chiffres).
  - DOC-005 : ligne RIB/ICE réécrite et logos aux extrémités effacés.
  - DOC-006 p1 : rangées de tableau fusionnées et artefacts `|` dans les traductions.
- **Cause.** D4 avait reclassé en texte des cadres qui structurent un formulaire. Les filets et cases, lus comme des glyphes `|`, `[`, `_`, se retrouvaient dans le texte envoyé au LLM.
- **Correction.** `backend/app/documents/line_verification.py::form_structure_evidence` détecte trois indices :
  - glyphes de filets en position structurelle (`ruling_glyphs`) ;
  - filet vertical traversant la ligne (`vertical_rules_crossing`) ;
  - filet horizontal entre deux lignes fusionnées (`horizontal_rule_between`).

  Un bloc à risque n’est ni envoyé ni réécrit : il garde ses pixels originaux, avec `FORM_STRUCTURE_PRESERVED` (warning) dans `backend/app/ai/translation/service.py::translate_blocks`.
- **Tests.** `backend/tests/unit/test_form_structure_guard_final.py`, 25 tests, dont :
  - `test_ruling_glyphs_only_at_structural_positions` ;
  - `test_vertical_rule_crossing_a_line_is_detected_but_glyph_strokes_are_not` ;
  - `test_horizontal_rule_between_two_lines_is_detected` ;
  - `test_structural_and_identifier_blocks_are_never_sent_nor_rewritten`.
- **Avant / après.** Run6 : champs DOC-007 fusionnés et réécrits → run17 : 32 blocs préservés `FORM_STRUCTURE_PRESERVED`, structure intacte (contrôle visuel dans `DOCUMENT_FIDELITY_REPORT.md` §3). Les caractères ainsi non traduits sont comptés dans la couverture stricte, sous la raison `form_structure`.

## D7 — Timeouts Tesseract sous charge

- **Symptôme (run2).** DOC-002 et DOC-007 en échec (`RuntimeError` du timeout manager) lorsque 3 groupes et pytest saturaient les 6 cœurs.
- **Cause.** Un timeout OCR unique, sans reprise.
- **Correction.** `TesseractOCR` : une seule reprise, tracée (`OCR_TIMEOUT_RETRIED`, info), avec un délai doublé plafonné à 300 s. Un second timeout échoue en mode fermé. Les autres erreurs ne sont pas reprises. Passages corpus exécutés avec `OMP_THREAD_LIMIT=1`.
- **Tests.** `backend/tests/unit/test_tesseract_timeout_retry.py`, 3 tests :
  - `test_timeout_is_retried_once_with_doubled_bounded_delay` ;
  - `test_second_timeout_fails_closed` ;
  - `test_other_errors_are_not_retried`.
- **Avant / après.** Run2 : 2 échecs OCR sur 8 → runs 3 à 17 : 0 échec (`error=null` pour les 8 documents en run17).

## D8 — Interim renvoie la source inchangée

- **Symptôme (run1 DOC-001, 2e passage).** Des blocs anglais revenaient non traduits, de façon non déterministe.
- **Cause.** Aucune détection d’une sortie verbatim pour une langue source connue autre que le français.
- **Correction.** `service.py::_retry_candidate` déclenche une seule reprise bornée (`UNCHANGED_TRANSLATION_RETRY`, info) si trois conditions sont réunies : langue connue non française, au moins 2 mots d’au moins 4 lettres, texte renvoyé tel quel. La reprise passe par le même `ContextPackBuilder` et le même garde budget 32K. Une sortie encore inchangée reste visible : elle n’est jamais masquée.
- **Tests.** `backend/tests/unit/test_interim_unchanged_retry.py`, 3 tests :
  - `test_verbatim_non_french_blocks_are_retried_once_and_applied` ;
  - `test_retry_is_bounded_and_verbatim_output_is_not_hidden` ;
  - `test_unknown_language_and_short_identifiers_are_not_retried`.
- **Avant / après.** Blocs anglais laissés en source (run1) → 25 reprises (83 blocs relancés) en run17, toutes bornées par le garde 32K.

## D9 — OCR illisible envoyé au LLM

- **Symptôme.** Zone illisible de DOC-007 p3 et bruit `©/N/ES` de DOC-006 p3 envoyés au modèle, avec à la clé des « traductions » de charabia.
- **Cause.** Aucun filtre de fiabilité OCR avant l’envoi.
- **Correction.** `segmentation.is_unreliable_ocr` (confiance < 0,45 et aucun mot d’au moins 4 lettres) marque `ocr_unreliable`. `service.translate_blocks` ne l’envoie pas et lève `OCR_UNRELIABLE_NOT_TRANSLATED` (warning) : la source est conservée.
- **Test.** `test_segmentation_final.py::test_unreadable_ocr_noise_is_flagged_and_not_a_merge_partner`.
- **Avant / après.** Charabia envoyé → 335 caractères (88 blocs `OCR_UNRELIABLE_NOT_TRANSLATED`, dont 4 issus de D25) non envoyés en run17, comptés dans la couverture stricte (raison `ocr_unreliable`).

## D10 — Faux `CONTEXT_OVERFLOW`

- **Symptôme (run3).** DOC-004 : 0 requête, 129 blocs `UNTRANSLATED`, 2 `CONTEXT_OVERFLOW` critiques. DOC-007 également touché.
- **Cause.** `backend/app/ai/context/builder.py::ContextPackBuilder.build_chunks` comptait l’unité complète (`_unit_json` : `source_lines`, `style_evidence`, géométrie), alors que le payload Interim ne transmet que `id/text/language`.
- **Correction.** `ContextPackBuilder._unit_wire` projette, pour le comptage des unités, les seuls champs réellement envoyés. La borne de la requête complète (entrée + sortie + marge ≤ 32 768) reste contrôlée par le garde moteur sur le message final, sans changement.
- **Tests.** `backend/tests/unit/test_context_wire_budget.py` :
  - `test_rendering_metadata_does_not_count_against_the_budget` ;
  - `test_genuinely_oversized_table_is_still_atomic_overflow` : un vrai dépassement reste bloquant.
- **Avant / après** (mesure o200k).
  - DOC-004, unité tableau : 38 522 → 2 676 tokens réels.
  - DOC-007 : 26 182 → 2 501.
  - DOC-004 : 0 bloc traduit (run3) → 85 (run4).
  - Run17 : 63 requêtes. Maximum réservé par requête : 20 988 ≤ 32 768. Maximum consommé : 2 498. 0 violation, 0 requête au-delà de 32 768 (réservé comme consommé).

## D11 — Surlignage perdu et date surlignée mal lue

- **Symptôme (audit run4, DOC-006).**
  - 12 surlignages roses non reproduits.
  - **Défaut critique :** une date sous surligneur, lue avec un chiffre du jour erroné par l’OCR primaire, était réécrite. La baseline la conservait, car elle gardait les pixels originaux.
- **Cause.** Le surlignage abaisse le contraste et Tesseract confond les chiffres. Aucune seconde lecture, aucun fond de surlignage n’était reproduit.
- **Correction.** Nouveau module `backend/app/documents/line_verification.py` :
  - `highlight_evidence` : surlignage par ligne, avec sa couleur ;
  - `second_reading` : lecture psm 7 sur le canal max(R,G,B) ;
  - `compare_readings`, `verify_lines`.

  Si les deux lectures sont en désaccord, le bloc n’est ni envoyé ni réécrit (`OCR_CRITICAL_ENTITY_DISAGREEMENT`, error). Le rendu remplit chaque ligne de sa propre couleur mesurée (`pdf_fidelity._plan_scan_block`).

  **Seconde itération (run5).** Appliquée à toutes les lignes chiffrées, la double lecture produisait de faux désaccords : sur DOC-002, 2 lectures primaires exactes, vérifiées visuellement, étaient contestées par une seconde lecture fausse sur du petit gras. Elle est donc **restreinte aux lignes sous surligneur**. Les autres lignes sont marquées `not_checked_no_marker` (explicitement non vérifiées, jamais « conformes »).
- **Tests.** `backend/tests/unit/test_line_verification_final.py`, 17 tests, dont :
  - `test_disagreeing_block_is_never_sent_nor_rewritten` ;
  - `test_clean_line_is_explicitly_not_checked_never_agreement` ;
  - `test_unavailable_reader_is_inconclusive_never_agreement` ;
  - `test_renderer_fills_highlighted_line_with_measured_colour_only`.

  `test_final_regression_gaps.py::test_real_second_reading_under_highlight`, en 2 cas, utilise le vrai Tesseract.
- **Avant / après.** Date DOC-006 réécrite fausse (run4) → bloc conservé en original avec alerte (runs 6 à 12). Surlignage : non reproduit → reproduit par ligne (vérifié visuellement sur DOC-006 p1 et p4).

## D12 — Lignes d’identifiants seuls réécrites

- **Symptôme.** Des lignes ne contenant que des dates, RIB/ICE, téléphones ou références passaient par le LLM et étaient réécrites, avec un risque d’altération de données critiques.
- **Correction.** `line_verification.identifier_only` : ces lignes restent en original, avec `IDENTIFIER_ONLY_KEPT` (info).

  **Défaut trouvé en run7.** La règle comptait comme acronymes les titres numérotés en majuscules : 45 blocs sur DOC-006, dont 33 titres. Elle a été corrigée : groupe d’au moins 3 chiffres et acronymes d’au plus 4 lettres. Résultat : 17 blocs sur le corpus.
- **Tests.**
  - `test_form_structure_guard_final.py::test_identifier_only_lines` ;
  - `::test_identifier_only_non_french_block_is_kept_with_info_issue`.
- **Avant / après.** Run7 : 45 blocs sur DOC-006 (faux positifs) → run17 : 25 blocs sur le corpus. La couverture « texte » les exclut des deux côtés (baseline et final) selon la même règle.

## D13 — Police démesurée sur les lignes contaminées par un cachet

- **Symptôme (run6, DOC-006 p4).** Lignes OCR traversées par un cachet tourné (confiance 0,56 à 0,74, hauteur 22 pt pour un texte de 9 pt), réécrites en police énorme.
- **Correction.** `pdf_fidelity._scan_font_size` : un titre de confiance < 0,8 (`SCAN_TRUSTED_SIZE_CONFIDENCE`) dont la taille propre dépasse le corps est ramené à la taille du corps. Un titre fiable garde sa taille.
- **Test.** `test_form_structure_guard_final.py::test_low_confidence_swollen_line_gets_body_size_but_confident_heading_keeps_its_own`.

## D14 — Lignes OCR traversant des zones séparées

- **Symptôme (audit run8, DOC-007 p1).**
  - En-tête traduit en géant (19,9 pt pour 7 pt) par-dessus le logo du ministère.
  - Ligne « travailleur » réécrite à travers 4 cellules.
- **Cause.** `TesseractOCR.image_to_blocks` fusionne `(block, par, line)` en une seule boîte, même avec 265 pt de blanc entre deux mots. Calibrage : 148 lignes du corpus présentent un blanc interne d’au moins 2 fois le corps, dont 71 étaient réécrites.
- **Correction.** `tesseract.split_line_at_gaps` coupe la ligne là où le blanc entre deux mots consécutifs atteint au moins 2 fois la hauteur médiane des mots (`LINE_SPLIT_GAP_FACTOR`). Les espaces justifiés restent sous 1 fois. L’ordre de lecture est conservé (RTL sûr). Chaque segment garde sa bbox et sa confiance, avec la trace `OCR_LINE_SPLIT_AT_GAP`.
- **Tests.** `backend/tests/unit/test_ocr_line_gap_split.py`, 5 tests, dont :
  - `test_line_is_split_where_the_blank_exceeds_twice_the_word_height` ;
  - `test_normal_and_justified_spaces_never_split` ;
  - `test_right_to_left_reading_order_is_kept_inside_a_segment`.
- **Avant / après.** Run9, premier passage avec le découpage :
  - superpositions : 14 (run8) → 6 ;
  - coupés/manquants : 138 → 111 ;
  - en-tête DOC-007 revenu à sa taille et à sa place (vérifié visuellement).

  Run17 (OCR de run10) : 204 lignes découpées (`OCR_LINE_SPLIT_AT_GAP`, info).

## D15 — Boîte de ligne gonflée par un fragment graphique

- **Symptôme (audit run9, DOC-007 p1).** Un fragment d’écusson, lu comme « 2 » en tête d’une ligne de 7 pt, gonflait sa boîte à 22,5 pt. Conséquences : police à 12,7 pt, et un masque qui mordait la ligne au-dessus (« DE TRABAJO »).
- **Correction.** `split_line_at_gaps` isole aussi tout « mot » d’au moins 2,2 fois la hauteur médiane (`LINE_SPLIT_TALL_WORD_FACTOR`), dans les lignes d’au moins 3 mots. Les variations dues aux ascendantes et descendantes restent inférieures à 2 fois.
- **Tests.** `backend/tests/unit/test_inflated_line_box_final.py` :
  - `test_tall_graphic_word_is_isolated_from_the_line_it_inflates` ;
  - `test_ascenders_and_descenders_never_isolate_a_word`.
- **Avant / après.** Boîte de 22,5 pt, police 12,7 pt (run9) → run17 : titres de section de DOC-007 p1 rendus à la taille du corps, sans gonflement (contrôle visuel des planches comparatives).

## D16 — Titre d’une ligne replié sur la rangée suivante

- **Symptôme (audit run9, DOC-007 p1).** Les titres de section mono-ligne (boîte de 14 pt, police 6,4 pt) étaient traduits sur 2 lignes, la seconde recouvrant les libellés de la rangée de tableau suivante.
- **Cause.** `_plan_scan_block` excluait des obstacles les boîtes qui chevauchent déjà la boîte du bloc. Une boîte OCR plus haute que l’impression laissait donc la traduction s’étendre sur la rangée suivante.
- **Correction.** Dans `pdf_fidelity._plan_scan_block`, une source d’une ligne reste sur une ligne : la hauteur des cadres candidats est limitée à 1,45 fois la police (`_SCAN_SINGLE_LINE_HEIGHT`). Le texte est réduit (jusqu’à 72 % au plus) ou étendu à droite.

  **Repli :** le retour à la ligne n’est permis que dans une zone **prouvée vide**. Il faut l’absence de tout bloc OCR, y compris ceux qui chevauchent la boîte, l’absence de zone protégée, et l’absence d’encre sur le raster (`_band_is_blank` : au plus 0,4 % de pixels sous 140). Trace : `SINGLE_LINE_WRAPPED_INTO_BLANK` (info). Sinon, `LAYOUT_OVERFLOW` critique, source conservée.

  **Défaut du correctif lui-même, trouvé en run11.** Le repli ne se déclenchait jamais : 0 sur 48 débordements. Un diagnostic hors ligne a montré que les cadres candidats réutilisés étaient trop courts pour 2 lignes sous des boîtes de 5 à 11 pt. Le contrôle d’encre n’était donc jamais appelé. Le repli construit désormais des cadres explicites de 2 et 3 lignes. Diagnostic : débordements mono-ligne DOC-004 4 → 3, DOC-007 11 → 6 ; encre mesurée 0 % pour les zones libres, 9 à 10 % pour les zones occupées.
- **Tests.** `test_inflated_line_box_final.py` :
  - `test_one_line_heading_in_a_tall_box_is_not_wrapped_onto_the_next_row` ;
  - `test_one_line_heading_without_room_reports_overflow_instead_of_wrapping` ;
  - `test_one_line_block_may_wrap_only_into_space_proven_blank` ;
  - `test_ink_under_a_one_line_block_forbids_the_wrap_fallback`.
- **Avant / après.** Titres DOC-007 repliés sur la rangée suivante (run9) → run17 : aucun titre replié sur la rangée suivante. 10 blocs repliés dans un blanc vérifié (`SINGLE_LINE_WRAPPED_INTO_BLANK`). Les cas sans place restent en source et sont signalés (`LAYOUT_OVERFLOW`).

## D17 — DOCX : hyperlien unique jamais traduit

- **Symptôme.** Un paragraphe constitué d’un seul `w:hyperlink` donnait `changed_count == 0`.
- **Cause.** `backend/app/documents/docx_fidelity.py::redistribute_text` traitait tout hyperlien comme une frontière ambiguë.
- **Correction.** Paramètre interne `allow_single_hyperlink`, activé uniquement par `edit_docx_package` lorsque tous les `w:t` appartiennent à l’unique hyperlien. La relation `r:id` n’est jamais réécrite. Les cas mixtes restent `REVIEW_REQUIRED`.
- **Tests.**
  - `backend/tests/unit/test_docx_final_audit_hyperlink.py` (1) : échec reproduit avant la correction, puis réussite ;
  - `test_docx_final_audit_invariants.py` (4) : règle du premier run, styles, listes, cellules fusionnées, en-têtes et pieds, images et relations, pagination LibreOffice, éditabilité.
- **Avant / après.** `changed_count` 0 → 1, `r:id` et relation conservés. 88 tests DOCX passent.

## D18 — Mesure de couverture gonflée

- **Symptôme.**
  - Le compteur `summary.untranslated_blocks` n’était pas fiable (run7 : 6 blocs annoncés pour 45 issues `UNTRANSLATED`).
  - Les blocs gardés volontairement (structure, identifiants, OCR peu fiable, désaccord) n’entraient pas dans la couverture, qui s’en trouvait gonflée.
  - La baseline affichait 0,9472 de couverture en caractères.
- **Correction.** L’outil versionné `tools/recette/measure_corpus_metrics.py` fournit :
  - la couverture **stricte** : tout bloc non français non traduit compte, quelle qu’en soit la raison ;
  - la couverture **texte** : lignes d’identifiants seuls exclues des deux côtés, selon la même règle que l’application ;
  - la ventilation `not_translated_chars_by_reason` ;
  - le texte source résiduel par OCR du candidat (200 dpi) ;
  - les zones visuelles comparées en union avec la référence ;
  - la déduplication des anomalies.

  `tools/recette/compare_visual_sheets.py` produit les planches original / ancien / nouveau / différence. Les deux outils refusent d’écrire dans le dépôt.
- **Avant / après.** Baseline recalculée de façon stricte : 0,8862 (au lieu de 0,9472), puis 0,8810 une fois la règle typographique D27 appliquée aussi à la baseline. Toutes les comparaisons de ce rapport utilisent la même définition des deux côtés.

## D19 — Réutilisation d’analyse sans réappliquer les vérifications

- **Symptôme.** Avec `--reuse-analysis`, le lanceur reprenait l’IR sans réappliquer la vérification des lignes : un correctif de règle n’était pas pris en compte.
- **Correction.** `tools/interim_owner_corpus_run.py::run_one` appelle `pipeline.run_line_verification`, qui est idempotente, sur l’analyse réutilisée.
- **Limite connue.** La réutilisation ne restaure pas les candidats visuels déjà retirés. Tout changement de protection ou d’OCR impose une analyse complète (runs 5, 9 et 10).

## D20 — Traduction dessinée par-dessus du texte source non masqué

- **Symptôme (audit run12, DOC-007 p1 et DOC-004).** Des traductions étaient écrites sur des restes de texte source que leur masque ne couvrait pas, ce qui rendait les deux illisibles.
- **Cause.** Les masques sont rétrécis loin des boîtes voisines (D3). La partie de la source située dans la zone rétrécie, ou de l’encre hors de tout bloc OCR, restait visible sous le nouveau texte. Aucun contrôle ne le détectait.
- **Correction.** `pdf_fidelity._drop_text_over_source_ink`, au point fixe, juste avant le dessin :
  - mesure, sous chaque ligne de glyphes réellement dessinée (`_drawn_line_rects`), l’encre originale qu’aucun masque prévu ne couvre (`_uncovered_source_ink`) ;
  - les filets de tableau (rangée ou colonne sombre à 70 % ou plus, `_RULE_RUN_SHARE`) sont exclus : ce sont de la structure, pas du texte résiduel ;
  - au-delà de 60 pixels et de 1 % de la surface mesurée (`_SOURCE_INK_MIN_PIXELS`, `_SOURCE_INK_MIN_SHARE`), l’item est écarté avec `SCAN_TEXT_OVER_SOURCE_INK` **critique** : l’original est conservé ;
  - le point fixe est itéré : écarter un item retire son masque, ce qui peut exposer de l’encre sous un voisin.
- **Tests.** `backend/tests/unit/test_source_ink_guard_final.py` :
  - `test_text_over_unmasked_source_ink_is_dropped_with_critical_issue` ;
  - `test_masked_source_ink_does_not_block_the_replacement` ;
  - `test_table_rule_through_the_line_is_structure_not_residual_text` ;
  - `test_ink_only_in_the_blank_part_of_a_grown_frame_is_not_under_drawn_text` ;
  - `test_fixed_point_drops_items_that_relied_on_a_dropped_neighbour_mask` ;
  - `test_native_pages_are_not_measured`.
- **Avant / après.** Run12 : superpositions sur source résiduelle, constatées visuellement → run13 : 54 items écartés, tous signalés critiques. **Coût mesuré** en run13 : couverture écrite dans le PDF 0,8324 → 0,7896 et mots source résiduels 146 → 234, puisque ces blocs restent en langue source. Ce coût a motivé D22.

## D21 — Bruit OCR d’écriture minoritaire envoyé au LLM

- **Symptôme (audit run12).** Sur des pages latines à faible confiance, des fragments lus dans une autre écriture (bruit de cachet ou de trame) étaient envoyés au modèle, qui en produisait des « traductions » sans objet.
- **Correction.** `line_verification.minority_script_noise` marque `minority_script_low_confidence` lorsque deux conditions sont réunies : l’écriture dominante du bloc représente moins de 15 % des lettres de la page (`MINORITY_SCRIPT_MAX_PAGE_SHARE`), et la confiance est inférieure à 0,7 (`MINORITY_SCRIPT_MAX_CONFIDENCE`). `service.translate_blocks` ne l’envoie pas et lève `OCR_SCRIPT_INCONSISTENT_NOT_TRANSLATED` (warning). Une page réellement bilingue (DOC-004) n’est pas touchée, car aucune des deux écritures n’y est marginale.
- **Tests.**
  - `test_source_ink_guard_final.py::test_minority_script_noise_rule` ;
  - `::test_verify_lines_marks_minority_script_noise_idempotently` ;
  - `::test_minority_script_noise_is_never_sent_and_is_reported`.
- **Avant / après.** Run13 : 7 blocs écartés, comptés dans la couverture stricte (raison `ocr_script_inconsistent`). Contrôle masqué sur DOC-004, DOC-007 et DOC-008 : uniquement du bruit. Run17 : 7 blocs (36 caractères), comptés dans la couverture stricte.

## D22 — Masques rétrécis devant des voisins eux-mêmes remplacés

- **Symptôme (mesure run13).** Sur les 54 items écartés par D20, la ventilation de l’encre non masquée donne : **39** relèvent de la source propre du bloc, 11 d’encre hors de tout bloc OCR, et 4 d’un voisin conservé en original (`/tmp/ink_origin.py`, outil de diagnostic privé non versionné).
- **Cause.** `_scan_covers` rétrécissait chaque masque loin de **toutes** les boîtes voisines qui le chevauchent. Cette règle n’a de sens que pour un voisin conservé en original. De plus, le dessin était séquentiel (masque, puis texte, item après item) : le masque d’un item ultérieur pouvait donc effacer un texte déjà dessiné.
- **Correction.** Dans `pdf_fidelity` :
  - `_plan_scan_block` calcule aussi, pour chaque ligne, le masque complet (`full_source_rects`, rétréci seulement loin des zones protégées) et les blocs voisins qu’il chevauche (`full_overlap_ids`) ;
  - `_apply_full_covers`, appelé à chaque itération du point fixe D20, retient pour chaque ligne le masque complet **uniquement si tous les voisins chevauchés sont eux-mêmes remplacés**, sinon le masque rétréci. Écarter un item ne peut que réduire les masques des autres, ce qui garantit que le point fixe termine ;
  - `render_pdf` dessine en **deux phases par page scannée** : tous les masques, puis tous les textes. Si une insertion finale diverge, la page est restaurée, l’item écarté (`LAYOUT_OVERFLOW` critique) et la garde D20 rejouée sur les items restants. Les pages natives gardent leur transaction par item ;
  - trace `SCAN_COVER_EXTENDED_OVER_REPLACED_NEIGHBOUR` (info).
- **Tests.** `backend/tests/unit/test_cover_growth_final.py` :
  - `test_full_cover_is_used_only_when_every_overlapped_neighbour_is_replaced` ;
  - `test_extended_cover_recovers_a_block_whose_own_source_was_left_unmasked` ;
  - `test_fixed_point_shrinks_back_the_cover_when_the_neighbour_is_dropped`.
- **Avant / après.** Rejeu hors ligne sur les traductions de run13, sans appel au modèle : items écartés par D20 54 → 37, et 42 lignes de masque étendues. DOC-007 p1 : la ligne d’activité, restée en espagnol en run13, est traduite proprement (vérifié en zoom). Run17 (nouvelles traductions) : 32 entrées (33 lignes) de masque étendu sur un voisin remplacé (`SCAN_COVER_EXTENDED_OVER_REPLACED_NEIGHBOUR`), et items écartés par D20 54 (run13) → 25.

## D23 — Filet de cellule ne dépassant la ligne que d’un côté

- **Symptôme (audit run13, DOC-007 p1).** Deux libellés de 5 pt, situés dans deux cellules adjacentes, étaient fusionnés par l’OCR en une seule ligne : le filet vertical de séparation était lu `|`, avec un début de ligne illisible. La ligne était réécrite en gras plus grand, à travers le filet.
- **Cause.** `line_verification.vertical_rules_crossing` n’acceptait qu’un filet dépassant la ligne **au-dessus et au-dessous**. Le séparateur d’une cellule part du filet horizontal supérieur, juste au-dessus du libellé : il ne dépasse que vers le bas.
- **Correction.** Une colonne sombre qui remplit toute la hauteur de la ligne et dépasse d’**un seul côté** d’au moins 0,35 fois la hauteur de ligne compte aussi comme filet. Un fût de glyphe ne sort jamais aussi loin de sa propre boîte de ligne. La détection sur deux côtés est conservée telle quelle : la règle est une extension stricte.
- **Calibration.** Sur le corpus entier, **1 seul bloc** est nouvellement marqué : le bloc fautif. Aucun faux positif (planche d’audit privée vérifiée).
- **Tests.** `test_cover_growth_final.py` :
  - `test_cell_separator_leaving_the_line_on_one_side_is_a_rule` ;
  - `test_glyph_stems_inside_the_line_box_are_not_rules` ;
  - `test_rule_crossing_on_both_sides_is_still_detected`.
- **Avant / après.** Run13 : ligne fusionnée réécrite à travers le filet → run17 : le bloc est préservé en source (`FORM_STRUCTURE_PRESERVED`, 31 → 32 sur le corpus) et le filet reste intact.

## D24 — Cadre agrandi dans de l’encre originale

- **Symptôme (audit run13, DOC-007 p1).** Un libellé de 5 pt (boîte de 4,5 pt) était écrit en 6 pt dans un cadre remonté de 5 pt, par-dessus le filet de la cellule.
- **Cause.** `_grow_vertical` et `_grow_right` ne connaissaient que les boîtes OCR comme obstacles. Bloqué en bas par la valeur de la cellule, le cadre remontait à travers le filet. La garde D20 ne le voyait pas, puisqu’elle exclut volontairement les filets.
- **Correction.** Dans `pdf_fidelity` :
  - `_page_dark` fournit un masque des pixels sombres de la page originale, mis en cache ; la planification précède tout dessin ;
  - `_ink_obstacles` place des obstacles à la première encre **séparée** au-dessus et au-dessous du bloc (sur sa largeur) et à sa droite (sur sa hauteur). Avec `_walk`, l’encre propre contiguë à la boîte OCR est absorbée (jusqu’à 0,35 fois la hauteur de ligne verticalement, 0,5 fois horizontalement), mais un filet qui touche la boîte (70 % ou plus) est un obstacle immédiat, jamais absorbé ;
  - `_growth_is_blank` rejette tout cadre candidat dont une bande hors de la boîte contient de l’encre (au moins 6 pixels et plus de 0,4 %), avec la trace `SCAN_FRAME_GROWTH_INK_REJECTED` (info). Sans cadre valide, le bloc passe en `LAYOUT_OVERFLOW` critique et la source est conservée.
- **Audit des rejets.** Planche privée de 12 rejets :
  - légitimes : texte arabe adjacent, ligne suivante, filets de cellule, cachet à droite ;
  - conservateurs sur DOC-006 p2, à cause de filets légèrement inclinés : les blocs concernés y restent placés grâce à un autre cadre candidat.
- **Tests.** `test_cover_growth_final.py` :
  - `test_horizontal_rule_above_the_box_stops_and_rejects_upward_growth` ;
  - `test_rule_touching_the_box_is_an_obstacle_never_absorbed` ;
  - `test_own_glyph_ink_past_the_ocr_box_is_absorbed_not_an_obstacle` ;
  - `test_ink_to_the_right_of_the_box_stops_right_growth`.
- **Avant / après.** Rejeu hors ligne, traductions run13 et D22 compris : items écartés par D20 37 → 22, débordements signalés 20 → 43 (DOC-004 5 → 19, DOC-007 7 → 14). **Arbitrage assumé :** une superposition illisible devient une non-traduction signalée. Run17 : 17 cadres rejetés (`SCAN_FRAME_GROWTH_INK_REJECTED`), items D20 25, débordements signalés 35, replis vérifiés 10.

## D25 — Fragment OCR de confiance nulle traduit et écrit

- **Symptôme (audit visuel run14, DOC-005 p1).** En pied de page, dans une zone surimprimée, un fragment lu avec une confiance OCR de **0,00** ressemblait à un mot de 5 lettres. Il a été envoyé au modèle, qui n’en a modifié que la ponctuation (espace français avant « : »). Le rendu l’a ensuite écrit par-dessus l’original.
- **Cause.** La règle D9 (`is_unreliable_ocr`) n’écarte un bloc à faible confiance que s’il ne contient aucun mot de 4 lettres ou plus. Une confiance mesurée quasi nulle n’était donc pas, à elle seule, un motif d’exclusion. De plus, ce drapeau n’était calculé qu’à la segmentation : une analyse réutilisée gardait l’ancienne valeur (même famille que D19).
- **Fichiers / fonctions.**
  - `backend/app/documents/segmentation.py` : `is_unreliable_ocr`, nouvelle constante `OCR_NO_CONFIDENCE = 0.10`.
  - `backend/app/documents/line_verification.py` : `verify_lines`, version `line-verification-4`.
- **Correction.**
  - Une confiance **mesurée** inférieure à 0,10 rend le bloc peu fiable, même s’il ressemble à un mot. Une confiance absente (`None`) garde la règle historique.
  - `verify_lines` recalcule le drapeau sur les blocs OCR, ceux qui ont des lignes source et une confiance mesurée. Il le fait dans le pipeline comme en réutilisation d’analyse. Le drapeau n’est jamais retiré, et le décompte est tracé (`blocks_ocr_unreliable_rechecked`).
  - Le bloc n’est pas envoyé au modèle. Ses pixels d’origine restent intacts et l’issue `OCR_UNRELIABLE_NOT_TRANSLATED` est levée (chemin D9 existant).
- **Tests.** `backend/tests/unit/test_ocr_no_confidence_final.py` (4) : règle sous le seuil, règle historique inchangée au-dessus (titres réels traduisibles, bruit écarté), recalcul sur une analyse réutilisée sans effet sur les blocs natifs, drapeau jamais retiré.
- **Avant / après.** Mesure sur le corpus run14 :
  - un seul bloc traduit et modifié avait une confiance inférieure à 0,10 ; les suivants (0,12 et plus) contiennent de vrais mots ;
  - rejeu de la règle sur les analyses : 4 blocs nouvellement marqués (DOC-004 ×3, DOC-005 ×1).
  - Run17 : 4 blocs marqués par le recalcul (`blocks_ocr_unreliable_rechecked`). Le bloc de DOC-005 garde sa source, avec `OCR_UNRELIABLE_NOT_TRANSLATED`.

## D26 — La reprise « inchangé » contournait la garde d’entités

- **Symptôme (run15, DOC-004).** 3 blocs portaient à la fois `PROTECTED_ENTITY_CHANGED`, une alerte critique de rejet, et `UNCHANGED_TRANSLATION_RETRY`. Leur traduction était pourtant appliquée. Pour l’un d’eux, la réponse appliquée modifiait la forme d’un identifiant critique (espacement d’un numéro), ce que seul l’évaluateur de fidélité a relevé (`CRITICAL_ENTITY_MODIFIED`).
- **Cause confirmée.** Interaction entre deux correctifs. `_restore_and_validate` remet la **source** quand une entité est modifiée. La reprise D8 sélectionne ensuite les blocs non français dont le résultat est identique à la source : elle prenait donc le rejet de la garde pour un écho inchangé du modèle, et renvoyait le bloc. Une seconde réponse qui passait le contrôle marqueurs/nombres était alors appliquée, alors que l’alerte critique du premier passage restait enregistrée et que le bloc figurait encore dans `untranslated_blocks`.
- **Fichier / fonction.** `backend/app/ai/translation/service.py`, boucle de validation et de reprise de `translate_blocks` (fonction interne `_translate_active`).
- **Correction.** Les blocs rejetés par la garde dans un appel sont mémorisés (`guard_rejected`) et exclus de la reprise. Ils gardent leur source et l’alerte critique, conformément à la décision de la garde. La reprise D8 reste réservée aux échos inchangés du modèle.
- **Test.** `backend/tests/unit/test_interim_unchanged_retry.py::test_entity_guard_rejection_is_not_retried_as_unchanged`. Un bloc dont le nombre est altéré n’est jamais renvoyé : la source est conservée, l’alerte posée et le bloc compté non traduit. Un écho inchangé voisin est, lui, relancé et appliqué.
- **Avant / après.** Run15 : 3 blocs rejetés puis appliqués après reprise (DOC-004). Run16 : 3 rejets `PROTECTED_ENTITY_CHANGED` sur le corpus, **0 traduction appliquée après rejet** ; les 3 blocs gardent leur source.

---

## D27 — Variante typographique de la source acceptée comme traduction
- **Symptôme (run16, DOC-008 et DOC-003).** Le modèle renvoyait pour des blocs non français la source elle-même, modifiée uniquement par la typographie française : espace insécable avant « : », espace ajoutée avant « ; ». Aucune alerte `UNTRANSLATED` n’était posée et le rendu réécrivait le même texte étranger par-dessus l’original. L’outil de mesure les classait en « inchangé sans alerte » ; l’application ne les signalait pas. Sur run16 : **15 blocs non français, 263 caractères** (DOC-001 ×1, DOC-002 ×1, DOC-003 ×1, DOC-004 ×2, DOC-005 ×4, DOC-006 ×5, DOC-008 ×1).
- **Cause confirmée.** Deux comparaisons trop strictes. Le contrôle `UNTRANSLATED` du pipeline (`evaluate_document`) testait `target == source` : une espace insécable suffisait à le contourner. La reprise D8 (`_retry_candidate`) compare par `split()`, qui absorbe l’espace insécable mais pas l’espace ajoutée avant « ; » ; le bloc de DOC-003 n’était donc même pas relancé.
- **Fichiers / fonctions.**
  - `backend/app/ai/translation/typography.py` (nouveau) : `typography_key`, `typography_equivalent`. Seules différences ignorées : formes de compatibilité Unicode, variantes d’espaces, espacement autour de la ponctuation, variantes de guillemets et tirets, casse. Un mot ou un chiffre différent n’est jamais équivalent.
  - `backend/app/ai/translation/service.py`, boucle de validation de `_translate_active`.
  - `backend/app/documents/pipeline.py`, `evaluate_document`.
  - `tools/recette/measure_corpus_metrics.py`, `_changed` (même règle pour la mesure, appliquée aussi à la baseline).
- **Correction.** Une sortie typographiquement équivalente à la source est remplacée par la **source exacte** et tracée (`TYPOGRAPHY_ONLY_OUTPUT_DISCARDED`, info). Le bloc redevient « inchangé » : il est relancé une fois s’il est éligible (D8), et s’il reste inchangé le pipeline pose `UNTRANSLATED` (erreur, `REVIEW_REQUIRED`). Le pipeline applique la même équivalence, en défense en profondeur pour les autres moteurs.
- **Tests.** `backend/tests/unit/test_typography_only_output_final.py` (10) : équivalence (espace insécable, espace fine, espacement, casse, guillemets et tirets, « ; ») ; vraie traduction et chiffre modifié jamais équivalents ; réponse typographique ⇒ source exacte et une reprise ; vraie traduction à la reprise appliquée ; `UNTRANSLATED` posé par `evaluate_document` sur une variante à espace insécable.
- **Avant / après.** Run16 : 15 blocs réécrits sans alerte. Run17 : 11 sorties typographiques ramenées à la source (DOC-001 ×1, DOC-002 ×1, DOC-004 ×1, DOC-005 ×4, DOC-006 ×4), relancées une fois si éligibles ; celles restées inchangées portent `UNTRANSLATED`. Blocs non français contenant des lettres et restés « inchangés sans alerte » (règle exacte de l’outil de mesure) : **13 en run16 → 3 en run17**. Les 3 restants sont de langue inconnue et non linguistiques : une adresse électronique, un code alphanumérique, un jeton de 2 lettres suivi d’une marque de direction. Effet attendu et assumé : la couverture stricte de DOC-005 baisse, car ces blocs ne sont plus comptés traduits.
---
## Audit de confidentialité avant commit (processus)

- **Symptôme.** Plusieurs tests de non-régression avaient été écrits en reproduisant des cas mesurés sur le corpus. Ils contenaient des fragments réels :
  - noms et prénoms ;
  - une phrase d’attestation avec date d’embauche ;
  - des numéros de téléphone et de fax ;
  - un numéro de compte bancaire et un identifiant d’entreprise ;
  - des dates, une ville, un pays et un nom d’organisation.

  Une docstring de `line_verification.py` citait aussi deux valeurs réelles.
- **Cause.** Pendant le débogage, des exemples de corpus ont été copiés dans les fixtures synthétiques. Une recherche par mots-clés ciblés ne les avait pas tous détectés.
- **Détection.** Contrôle systématique avant commit : chaque chaîne littérale des fichiers ajoutés ou modifiés (n-grammes de 3 mots, nombres d’au moins 6 chiffres, mots capitalisés) a été comparée au texte OCR des 8 analyses réelles.
- **Correction.**
  - Valeurs synthétiques de même forme et de même longueur : noms fictifs, numéros de téléphone dans la plage réservée à la fiction, compte et identifiant factices, dates modifiées en conservant le type d’erreur OCR testé.
  - Les tests concernés ont été rejoués, puis la suite complète.
  - La docstring a été réécrite sans valeurs ; l’AST du module est inchangé.
- **Vérification.**
  - `git log --all -S` : aucun de ces fragments n’a jamais été committé ni poussé.
  - Le contrôle systématique ne trouve plus que du vocabulaire générique de formulaire.

## Défauts restants et limites (non corrigés, documentés)

1. **Absence de référence humaine.** Aucune référence de traduction validée par un humain. `translation_score` et `semantic_score` valent `NULL`, et les 8 documents sont `REVIEW_REQUIRED`. Aucun CER/WER n’est revendiqué.
2. **Faux positif conservateur sur DOC-006.** Ligne de cachet (date collée au mois, valeur expurgée en RUN28) : la traduction modifiait l’entité (`PROTECTED_ENTITY_CHANGED`). Elle n’est pas appliquée et l’alerte reste visible.
3. **Petits libellés de formulaire (police d’environ 5 pt).** Des erreurs OCR primaires y subsistent : par exemple, DOC-007 « EMPRESA » lu « EXPRESA », d’où une traduction erronée. La double lecture n’est faite que sous surligneur (D11). Les lignes propres sont `not_checked_no_marker`, c’est-à-dire non vérifiées.
4. **Blocs minuscules.** Les blocs de 3 à 10 pt de large qui ne peuvent contenir leur traduction restent en `LAYOUT_OVERFLOW`, source conservée. Run17 : 35 débordements signalés sur le corpus.
5. **Surlignage dans les cellules scannées.** La voie des cellules de tableau scannées n’applique pas la couleur de surlignage par ligne. La voie bloc l’applique.
6. **Superpositions de cadres agrandis.** Depuis D24, un cadre ne croît plus dans l’encre originale. En revanche, les cadres agrandis de deux blocs voisins ne sont pas mutuellement exclus. Les superpositions résiduelles sont mesurées et signalées (`RENDER_TEXT_OVERLAP`).
7. **Faux positifs de langue sur DOC-003 (français).** 3 lignes courtes, en-tête et titre en majuscules, ont été détectées comme non françaises. Faux positifs du détecteur, documentés et non masqués.
8. **Qwen privé.** Endpoint, tokenizer et poids non disponibles. La compatibilité est conservée par l’interface du fournisseur et le budget 32K, sans exécution réelle.
9. **Coût des gardes.** Les gardes de structure (D6, D23), d’encre (D20) et de croissance (D24) privilégient l’intégrité visuelle sur la couverture. Les blocs concernés restent en langue source, signalés et comptés dans la couverture stricte et la couverture écrite.
10. **Libellés de 5 pt en cellule.** Un libellé plus petit que la police minimale lisible (6 pt) ne peut pas toujours tenir dans sa cellule sans croître. Il reste alors en `LAYOUT_OVERFLOW`, source conservée (D24).
11. **Faux positif de l’évaluateur de tableaux (DOC-001 p2, run14 et run17).** L’évaluateur PDF indépendant détecte une « table » 2×2 sans bordure dans le candidat : 4 traductions insérées, à environ 550 pt d’écart. La source scannée n’a pas de couche vectorielle, donc pas de table. Il en résulte `PDF_TABLE_STRUCTURE_CHANGED`. L’alerte est **laissée critique**, sans assouplir la règle en fin de mission. L’évaluateur devrait ignorer les tables candidates sans bordure dont les lignes sont incompatibles avec une table (amélioration proposée, non faite).
12. **Solde non attribuable.** 32 blocs traduits (run17) ne sont pas retrouvés dans le PDF candidat sans qu’une garde de débordement ou d’encre ne les signale bloc par bloc (contre 59 en baseline). Causes probables : items multi-blocs, comme les cellules de tableau rendues bloc par bloc, ou appariement géométrique de l’évaluateur. Ils sont comptés comme non écrits dans la couverture écrite, et l’alerte agrégée `RENDER_*_MISSING` reste critique.
13. **Sorties inchangées sans alerte spécifique.** 121 caractères en run17, comptés comme non traduits dans la couverture stricte (raison `unchanged_no_issue`), donc jamais comme traduits. Depuis D27, seuls 3 de ces blocs contiennent des lettres (adresse électronique, code alphanumérique, jeton de 2 lettres, tous de langue inconnue). Les autres sont des chiffres ou des symboles sans lettres, que l’application ne considère pas comme à traduire.
14. **Faux positifs de langue sur DOC-005 (document français).** 31 fragments courts sont détectés non français : 29 font au plus 3 mots, le plus long 6, et aucun ne contient de mot-outil d’une langue étrangère. Ce sont très probablement des noms, adresses ou codes, que le modèle laisse inchangés à juste titre. Ils portent `UNTRANSLATED` (revue requise). La couverture stricte de DOC-005 (0,0828) est donc **pessimiste** : elle ne mesure pas une perte de traduction. Sa valeur baseline (0,7494 avant D27) était gonflée par des variantes typographiques comptées comme traductions.
15. **Non-déterminisme du modèle.** Chaque passage obtient de nouvelles réponses Interim. À analyse identique (run10), les compteurs de rendu varient d’un passage à l’autre : par exemple, débordements signalés 32 (run16) → 35 (run17). Les chiffres de ce rapport sont ceux de run17 et ne constituent pas une moyenne.
16. **Nom de fichier imprimé traduit (DOC-006 p16).** Un nom de fichier imprimé en pied de page est traduit comme du texte. Aucune garde ne protège les noms de fichiers. Amélioration proposée : ajouter le motif « nom de fichier avec extension » aux entités protégées.
17. **Unité modifiée (DOC-006, 1 bloc).** L’unité « m » (×2) est absente de la cible, alors que les 4 « % » du bloc sont conservés. L’alerte `HALLUCINATION_UNIT_CHANGED` reste critique et ce bloc relève de la revue humaine.
18. **Masques trop grands sur DOC-006 (12 → 24).** Les masques par ligne des lignes surlignées dépassent la marge tolérée par l’évaluateur. Ils sont signalés en `RENDER_TEXT_MASK_TOO_LARGE` / `VISUAL_MASK_TOO_LARGE`. Leur ajustement aux glyphes n’a pas été fait dans cette phase.
