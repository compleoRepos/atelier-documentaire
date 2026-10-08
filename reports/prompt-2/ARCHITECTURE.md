# Architecture de fidélité documentaire — extension prompt 2

L’architecture FastAPI / Angular / PostgreSQL / S3 / Celery / Qwen privé reste inchangée. Aucun nouveau serveur, endpoint public, service Docker ou volume n’est ajouté.

## Flux intégré

```text
Original immuable + SHA256
  ├─ DOCX ZIP/OOXML → collect_docx_content
  │    → paragraphes/runs/propriétés/header/footer/nested tables
  │    → source_ref xml_part + paragraph_path numérique
  └─ PDF/image → ingestion/OCR existante + layout candidates
       → enrich_tables (dessins/textes source, fills/borders/align/padding)
       → protected_visual_regions (original-only, provenance candidate)

IR + traductions indexées block_id
  → reconstruct_document (vérification SHA, refus source/out alias)
    ├─ edit_docx_package → redistribute_text → ZIP candidat
    │    (w:t uniquement, structure intacte, multistyle review)
    └─ render_pdf → unité cellule → préflight → redactions glyphes
         → insertion zone intérieure → rollback si divergence

Candidat réel
  → parse_docx_structure + compare_ooxml_integrity
  → compare_pdf_tables source/candidat indépendant
  → conversions LibreOffice / rendus PDF réels
  → géométrie, contenu cellule, pixels protégés, masques glyphes bornés
  → evaluate_document + fidelity_scores
  → artefacts privés original/translated/diff/metrics/result
  → REVIEW_REQUIRED → reviewer existant (pas auto-approbation)
```

## Modules ajoutés

| Module | Responsabilité |
| --- | --- |
| `docx_analysis.py` | Ingestion hiérarchique originale, tables imbriquées, parties header/footer, métadonnées runs et refs XML stables |
| `docx_fidelity.py` | Redistribution traçable, refus champs/frontières ambigus, édition package sans aplatissement |
| `ooxml_integrity.py` | Comparaison indépendante de toutes les parties, canonisation XML hors texte et xml:space |
| `pdf_fidelity.py` | Enrichissement table/style, rendering cellule, preflight/rollback, comparaison géométrie/contenu réelle |
| `protected_visuals.py` | IR original-only protégé, validation bbox, images/widgets/vecteurs candidats |
| `fidelity_report.py` | Résumé scores avec inconnus explicites, artefacts privés par page |
| `tools/prompt2_fidelity_measure.py` | Mesure synthétique avant/après avec vrai pipeline de base, analyse corpus privée reproductible |

## Interfaces pour le coordinateur / branche 1

### `pipeline.py` partagé

Conserver les signatures historiques `analyze_document(source_path, work_dir, options=None)`, `reconstruct_document(ir, translations, output_path, protected_regions=None)`, `evaluate_document(...)`, `translate_document(...)`.

Les changements de cette branche concernent `_tables` enrichissement, `_docx_ir`, remplacement DOCX, `_reconstruct_docx`, `reconstruct_document`, normalisation `reference_status` et appel artefacts dans `translate_document`. La suppression de lignes du renderer legacy est une délégation au nouveau module, pas suppression de fonctionnalité. La petite correction `_native_blocks` conserve les tokens courts (A/B/1) : une cellule ne peut pas être entièrement réécrite si l’IR a omis du contenu natif. Préserver cette correction lors du merge avec ingestion branche 1.

### IR compatible

- Schéma reste extensible `1.0`. Champs ajoutés, aucun champ historique supprimé.
- Blocs DOCX : `runs`, `properties`, `hyperlinks`, `bookmarks`, `fields`, `field_result_protected`, `tabs`, `breaks`, `parent_id`, `order`, `source_language`, `target_language`, `translation_status`.
- `source_ref.xml_part` désigne la partie du package ; `paragraph_path` est une **liste d’indices enfant 0-based** depuis la racine XML. Les identifiants top-level historiques sont conservés. Tables imbriquées : identifiants distincts et `parent_id` cellule.
- Cellules DOCX : `row_span`, `column_span`, `grid_span`, `v_merge`, `merge_parent_id`, `paragraph_ids`, **`block_ids`** (même liste, utilisée pour chunks atomiques), `table_ids`, `style_xml`. Lignes `row_records` ; `grid_widths`/table `style_xml` originaux.
- Visuels : `protected_visual_regions` liste `{type:'protected_visual', subtype, bbox, page, source_id, editable:false, provenance, authenticity_verified:false, coordinates_kind:'original'}`.
- `images` DOCX contient aussi les media originaux protégés et SHA ; bbox inconnue reste null, jamais inventée.
- Traduction des nested tables : branche 1 doit grouper récursivement `table_ids` sans dupliquer les mêmes paragraphes entre plusieurs chunks. Le builder legacy groupe déjà les `block_ids` ; parent/nested grouping complet reste interface à finaliser.

### OCR/preprocessing

Le renderer ouvre **toujours `ir.source_path` original**, jamais une working copy OCR. Les bbox doivent être exprimées en coordonnées originales ; toute homographie/orientation/crop utilisée par branche 1 exige transformation inverse avant création des blocks/table/protected regions. Fusionner les zones explicites et détectées ; ne jamais reclassifier une image de page entière en signature certaine. Les candidats non validés restent candidates.

### Résultat de rendu

`renderer_version`, `redistribution_trace`, `table_render_trace`, `table_structure` **extrait candidat**, `structure_metrics`, `pdf_structure`, `geometry_metrics`, `protected_region_results`, `text_masks`. Les traces peuvent contenir du contenu documentaire : stockage privé uniquement, jamais reports Git ni logs d’audit centraux.

### Qualité / revue

- `document_fidelity` étend `translation.json` et conserve quality existant.
- STRUCTURE_SCORE/TABLE_SCORE = preuves structurelles et graphiques techniques, pas validation sémantique du tableau.
- TEXT_SCORE = présence du texte demandé dans le rendu, pas qualité linguistique.
- VISUAL_SCORE = moteur existant ; GLOBAL_SCORE reste null sans providers/calibration/validation humaine.
- Provider brut `reference_status=not_available` reste visible dans `quality_contract`; API pipeline expose `not_evaluated` sans référence.
- `APPLIED` n’est pas `APPROVED`. Multistyle avec redistribution est `REVIEW_REQUIRED`, sans faux semantic_alignment.
- Si LibreOffice/preuve indisponible : null et `NOT_AVAILABLE_IN_ENVIRONMENT`, jamais 1 par défaut.

## Confidentialité et exploitation

`dataset/input`, metadata, `test-report/prompt-2`, runtime, .env, models et previews sont exclus de Git. Les huit PDF originaux ont été récupérés par URLs privées autorisées ; aucun transfert public. Rapports Git ne contiennent que données synthétiques et agrégats non identifiants. Aucun endpoint/poids/tokenizer privé n’est inventé. Les services de l’autre exécution ne sont ni touchés ni reconfigurés.

## Vérification des interfaces P1 publiée (lecture seule)

La branche distante P1 a été consultée au commit `69be1300451f48d4c2847549d077e84ee9f5dd01`, sans checkout/rebase/cherry-pick/merge. `preprocessing.py` fournit `ProcessingResult(image, ocr_result, metadata, protected_visual_regions, warnings)`, `map_bbox(...)`, matrices `transform_source_to_processing` et `transform_processing_to_source` 3×3, tailles source/processing et previews/snapshots. Le pipeline P1 mappe les OCR bbox et zones vers les coordonnées page source. `raster_adapter.py` fournit `raster_pdf_copy(...)` pour TIFF et conserve les pixels/SHA source.

Le coordinateur doit conserver ces transformations et candidats, puis appeler `protect_ir` de P2 **après le retour en coordonnées originales**. P2 fusionne déjà les candidats `ir.protected_visual_regions` existants, ses détections indépendantes et les annotations explicites, avec déduplication page+bbox+source_id. P1 utilise `type=protected_visual_region`, P2 normalise `type=protected_visual` ; les extra-métadonnées de provenance/candidat sont conservées. Les types d’affichage peuvent être harmonisés par le coordinateur, sans changer la signification `editable=false`, coordinates source/original et authenticité inconnue.

Le mapping OCR n’est pas la preuve graphique : la reconstruction P2 ne lit que le document source original et vérifie les pixels des régions source. Les fichiers de preprocessing/snapshots restent privés. Toute homographie ou région hors page non validée est un blocage de revue.

Au 8 octobre 2026, l’utilisateur autorise un provider temporaire Interim (gpt-5-mini/proxy) sur **documents synthétiques uniquement**, implémenté par P1. P2 ne fait aucun appel LLM ; ses cibles de fixtures sont déterministes. Aucun des huit PDF RH ni leur texte/IR/preview n’a été transmis à Interim/OpenAI ou un autre service externe. La validation Qwen privée reste indisponible dans cette exécution.
