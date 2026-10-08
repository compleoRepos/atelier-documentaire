# Fichiers modifiés — prompt 2

## Sources

| Fichier | Modification et motivation |
| --- | --- |
| `backend/app/documents/pipeline.py` | Intégration des modules dédiés sans changer signatures publiques ; DOCX XML hiérarchique, package editing, PDF cellule, SHA et alias, protected regions, candidat table réellement extrait, référence absente not_evaluated, renderer versions et artefacts. Ingestion PDF/image/OCR conservée, sauf inclusion des petits tokens natifs nécessaires aux cellules. |
| `backend/app/documents/render_metrics.py` | Comparaison OOXML package hors texte, tableaux PDF relus indépendamment, cible cellule exacte, dimensions masques par page, NOT_AVAILABLE_IN_ENVIRONMENT si rendu impossible. |
| `backend/app/documents/docx_analysis.py` | Nouveau : DOCX hiérarchique, tables imbriquées, rows/cells/paragraphs/runs, fusions, parties header/footer/notes/comments et wrappers Word, refs XML numériques, media SHA. |
| `backend/app/documents/docx_fidelity.py` | Nouveau : redistribution proportionnelle tracée, champs/frontières ambigus protégés, namespaces Word stricts, package preservation, refs bornées, champs traversant paragraphes. |
| `backend/app/documents/pdf_fidelity.py` | Nouveau : styles candidats tirés des dessins, cellule entière avec zone intérieure, preflight/rollback, bordures/fills originaux, refus coverage/ambiguïté, comparaison tables/targets indépendante. |
| `backend/app/documents/protected_visuals.py` | Nouveau : régions originales protected_visual, bbox validées, images/widgets/vecteurs candidats et coverage gap scans. |
| `backend/app/documents/ooxml_integrity.py` | Nouveau : invariants toutes parties package et structure non textuelle par canonisation indépendante. |
| `backend/app/documents/fidelity_report.py` | Nouveau : scores techniques sans GLOBAL inventé, previews/diff/metrics/result privés. |
| `tools/prompt2_fidelity_measure.py` | Nouveau : vraie comparaison baseline git show / candidat sur fixtures synthétiques et option corpus privé, aucun LLM. |

## Tests

`backend/tests/unit/test_audit_guards_prompt2.py` : couverture wrappers/notes, blocs inchangés disparus, mauvaise page/sous-mot, plages textuelles disjointes sans double preuve, bbox hors page, vecteurs internes de cellule.

- `backend/tests/unit/test_docx_fidelity_prompt2.py` : redistribution/styles, XML/ZIP, champs, nested textbox, namespaces, types/ref négative, résultat multi-paragraphes protégé.
- `backend/tests/unit/test_pdf_fidelity_prompt2.py` : grille fusionnée, styles/fill/bordures/cell targets, overflow, visuels, multi-pages, rollback forcé.
- `backend/tests/unit/test_protected_visuals_prompt2.py` : bbox fail-closed, image originale, widget/form value, SHA, alias original/out.
- `backend/tests/unit/test_context_limits_prompt2.py` : seuils 10K/20K/22K/25K/30K/31K/32K/32K+ sur tokenizer de comptage explicitement synthétique ; refus transport oversize, aucune réponse Qwen simulée.
- `backend/tests/unit/test_fidelity_measurements_prompt2.py` : suppression tables/fill altéré/target absent, OOXML taille altérée, masque dimensions multi-page, preuve manquante, masque trop large, artefacts et null non-PASS.
- `backend/tests/integration/test_fidelity_prompt2.py` : DOCX complet, fusions/nested tables/cellules vides/media/header/footer/multi-style, pagination LibreOffice réelle.

**Aucun test préexistant supprimé ou relâché.** Les corrections de tests nouveaux en cours d’implémentation ont ajusté uniquement les contrats du nouveau code (appel max_output requis, attente multistyle review avec redistribution), jamais transformé un échec préexistant en PASS par changement d’assertion.

## Documentation / contrat machine

- `docs/architecture.md` : extension de fidélité, lien vers contrat de merge.
- `reports/prompt-2/AUDIT.md`, `ARCHITECTURE.md`, `TEST_REPORT.md`, `DOCUMENT_FIDELITY_REPORT.md`, `CHANGED_FILES.md`.
- `reports/prompt-2/SYNTHETIC_MEASUREMENTS.json` : données exclusivement synthétiques, pas chemins corpus/personnels.
- `reports/prompt-2/EXECUTION-RESULT.json` : signal final attendu par coordinateur, comptages réels et blocages explicites.

## Exclus et non modifiés

Aucun PDF original, IR personnel, preview corpus, métadonnée personnelle, .env, clé, modèle ou poids n’est ajouté à Git. Tout corpus/diff/OCR et logs bruts est sous `test-report/prompt-2/` ou `dataset` déjà ignorés. Frontend, configuration Qwen, preprocessing, glossaire/mémoire, endpoints API, services/ports/volumes Docker de l’autre exécution, branche 1 et `main` ne sont pas modifiés.
