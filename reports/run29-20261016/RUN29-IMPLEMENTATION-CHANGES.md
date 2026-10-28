# RUN29 — Modifications du code et justification

Base : tête RUN28 `0198654`. Branche : `feature/run29-correction-bout-en-bout-20261016`. Aucune formule, aucun poids ni aucun seuil de score n'a été modifié. Aucune migration de base de données. L'interface Angular n'a pas été modifiée en RUN29.

## 1. Fichiers modifiés

| Fichier | Lignes (+/−) | Correctifs | Justification |
|---|---|---|---|
| `backend/app/documents/pdf_fidelity.py` | +523 / −5 | F43, F44, F45, F48, F48b, F50, F50b, F50c, F53 | causes racines D3, D4, D5, D7, D8, D16 du rendu scan (masquage, replis de taille, texte barré par un filet) |
| `backend/app/documents/render_metrics.py` | +193 / −0 | F49 | aucune métrique ne détectait un filet de tableau effacé (D6) |
| `backend/app/ai/translation/service.py` | +59 / −10 | F46, F47, F52 | moteur privé inutilisable ou fragile (D10, D11, D12) |
| `backend/app/documents/ocr_recovery.py` | +22 / −1 | F51 | preuve lexicale trop faible acceptée à très basse confiance OCR (D9) |
| `backend/app/documents/block_status.py` | +3 / −1 | F50, F53 | nouveaux motifs explicites `render_source_glyphs_cut` et `render_text_crosses_rule` ; version `block-status-6` |
| `backend/requirements.txt`, `backend/pyproject.toml` | +3 / −0 | F46 | `jinja2==3.1.6` déclaré (nécessaire au gabarit de conversation du tokenizer) |
| `tools/interim_owner_corpus_run.py` | +61 / −12 | comparaison des moteurs | option `--engine private` : même service, même IR, mêmes prompts et budgets, seul le moteur change ; nouvelles inférences seulement (ni mémoire ni rejeu) ; autorisation des originaux toujours exigée |
| `backend/tests/unit/test_run27_render_regressions.py` | +7 / −1 | isolation | un test historique F31 désactive explicitement F50 par interrupteur ; **assertions inchangées** |
| `backend/tests/unit/test_run28_render_regressions.py` | +3 / −0 | isolation | un test historique F37 désactive explicitement F45 ; **assertions inchangées** |

Total : 10 fichiers modifiés (+874 / −30) et 6 fichiers de tests ajoutés (1 267 lignes).

## 2. Nouveaux fichiers de tests

| Fichier | Lignes | Objet |
|---|---|---|
| `backend/tests/unit/test_run29_layout_regressions.py` | 252 | F43, F44, F45 (scènes synthétiques, abstentions, contre-épreuves par interrupteur) |
| `backend/tests/unit/test_run29_render_regressions.py` | 464 | F48, F48b, F49 (dont 2 cas de bout en bout par `measure_render_fidelity`), F50, F50b, F50c |
| `backend/tests/unit/test_run29_ocr_regressions.py` | 46 | F51 |
| `backend/tests/unit/test_run29_private_engine.py` | 156 | F46, F47 avec un **vrai** tokenizer `transformers` construit en mémoire, aucun réseau |
| `backend/tests/unit/test_run29_private_chunking.py` | 132 | F52 avec un moteur privé **factice identifié comme tel** (aucun réseau) |
| `backend/tests/unit/test_run29_rule_crossing.py` | 217 | F53 (détection des filets visibles, lignes réellement dessinées, filet à la ligne de base admis, câblage du refus, interrupteur) |

Les décomptes exacts par fichier, issus du JUnit de la suite finale, figurent dans [RUN29-TESTS.md](RUN29-TESTS.md).

## 3. Description des correctifs

### Masquage et reconstruction scan (`pdf_fidelity.py`)

| Code | Comportement ajouté | Garde-fous | Interrupteur |
|---|---|---|---|
| F43 | dégagement de 1 pt (0,45 pt d'anticrénelage) entre une couverture papier et une zone protégée (case à cocher, signature, tampon) | appliqué seulement si la bande retirée est prouvée vierge sur le raster d'origine ; sinon comportement RUN28 | `_PROTECTED_CLEARANCE` |
| F44 | une ligne unique qui déborde peut être rendue sur deux lignes à taille réduite bornée, dans l'espace compris entre ses voisins les plus proches | essai **après** le repli condensé RUN28 (F37) ; espace prouvé vierge hors couverture ; abstention si un voisin croise la zone d'impression ; code `SINGLE_LINE_WRAPPED_BETWEEN_NEIGHBOURS` | `_SCAN_WRAP_BETWEEN_NEIGHBOURS` |
| F45 | dernier recours avant `LAYOUT_OVERFLOW` : interligne serré 1,0 (régulier puis condensé) | jamais avant les replis existants ; code `SCAN_TIGHT_LINE_HEIGHT` | `_SCAN_TIGHT_LINE_HEIGHT` |
| F48 | le test de continuité des filets (F38) ponte les trous de numérisation de ≤ 3 px (zoom 2) | le test de prolongement reste mesuré sans pont | `_RULE_GAP_PX` |
| F48b | le pont n'est appliqué qu'aux filets vérifiés sur ≥ 20 pt | évite de prendre le fût d'une lettre grasse pour un filet | `_RULE_BRIDGE_MIN_PT` |
| F50 | une couverture qui laisse des fragments de glyphes source orphelins (hors de toute boîte OCR) est refusée | refus = original conservé à cet endroit + anomalie critique `SCAN_COVER_CUTS_SOURCE_GLYPHS` + motif `render_source_glyphs_cut` | `_CUT_GLYPH_CHECK` |
| F50b | les fragments minces et longs (filets) sont exclus de F50 | ils relèvent de F49 | `_CUT_GLYPH_RULE_*` |
| F50c | une composante effacée à ≥ 50 % dont un reste reste visible est comptée, même dans une boîte OCR | mêmes seuils de refus que F50 | `_CUT_GLYPH_OWN_CHECK` |
| F53 | avant d'accepter un placement, les lignes réellement dessinées par PyMuPDF (mesurées sur une page vierge) sont confrontées aux filets fins (≤ 2,5 pt, ≥ 15 pt et ≥ 30 % de la largeur du cadre) restés visibles hors des couvertures ; un filet qui traverse le corps des lettres (0,1 à 0,5 corps au-dessus de la ligne de base, recouvrement ≥ 3 pt) fait refuser le placement | un filet à la ligne de base (effet souligné) reste admis ; refus = original conservé + `SCAN_TEXT_CROSSES_RULE` critique + motif `render_text_crosses_rule` | `_SCAN_CHECK_TEXT_OVER_RULES` |

Le repli nominal et le repli condensé F37 sont **textuellement identiques** à RUN28 : les nouveaux replis s'ajoutent après eux. Un premier ordonnancement de F44 (avant F37) avait fait passer à tort deux lignes déjà correctes en deux lignes ; cette régression, observée au rejeu, a été corrigée avant la mesure finale.

### Évaluation (`render_metrics.py`)

| Code | Contrôle | Limites connues |
|---|---|---|
| F49 `RENDER_RULE_ERASED` (critique) | filets fins et longs (≥ 30 pt, trous de ≤ 2 px refermés) qui se prolongent hors des masques (≥ 4 pt) et sont effacés sous les masques sur ≥ 8 pt contigus, horizontaux et verticaux ; le signalement localise le plus long segment effacé | filets épais (≥ 2 pt) non contrôlés (limite figée par un test) ; rappel non mesuré faute de référence |

### Moteur privé (`service.py`)

| Code | Correctif |
|---|---|
| F46 | toute erreur du contrôle préalable (gabarit de conversation, dépendance absente) devient une anomalie critique **sans appel réseau** |
| F47 | comptage de jetons lu sur `input_ids` (`BatchEncoding` de `transformers` 5) ; tout type indéterminé est refusé (fail-closed) |
| F52 | plafond de blocs par requête (`private_ai_max_blocks_per_request`, 40 par défaut) et redécoupage borné (profondeur 5) sur dépassement de contexte, sortie invalide ou identifiants manquants ; code `PRIVATE_CHUNK_SPLIT_RETRY` ; le mode Interim est inchangé |

### Validation OCR (`ocr_recovery.py`)

| Code | Correctif |
|---|---|
| F51 | sous une confiance OCR de 0,35, un unique mot connu de 5 lettres au plus n'est pas une preuve lexicale : le bloc passe en revue humaine (`ocr_unreliable`) et l'original est conservé |

## 4. Ce qui n'a volontairement pas changé

- Formules, poids, seuils et inconnues des scores v1 et v2 : inchangés. Les deux règles de mesure (RUN28 et RUN29) donnent des valeurs identiques sur les mêmes artefacts.
- Mode Interim, autorisation privée des originaux, garde de budget 32K et mémoire de traduction : inchangés.
- Façonnage RTL, segmentation des phrases RTL, `model_returned_source` : diagnostiqués, non corrigés (voir [RUN29-OPEN-ISSUES.md](RUN29-OPEN-ISSUES.md)).
- Parcours Office (DOCX/XLSX/PPTX) et interface Angular : non modifiés en RUN29.

## 5. Empreintes

Empreintes tronquées (16 caractères) calculées par les lanceurs privés sur le contenu des fichiers ; elles identifient l'arbre exact de chaque exécution et ne concernent aucun document du corpus.

| Arbre | Code produit | Tests | Usage |
|---|---|---|---|
| RUN28 (base, commit `0198654`) | `914d925722133d4d` | — | baseline `run29a` |
| F43–F47 (copie figée) | `a5f78d32ca9a5317` | — | première passe gpt-oss `run29oss` et contre-passe Interim `run29m` |
| F43–F51 | `365d4c7aa94c0e7c` | `5de45878048620ea` | `run29h`, suite et golden run29a |
| F43–F52 | `67dffd94acfcab8a` | `88e89ab66dc882ed` | `run29i`, passes gpt-oss `run29oss2` (copie équivalente) et `run29oss3`, suite run29b |
| **F43–F53 (final)** | **`3846f2296a271396`** | **`efadfa6a14d7a9f9`** | **verdict `run29j`, suite et golden run29c** |

| Règle de mesure | Empreinte | Résultat sur les mêmes artefacts |
|---|---|---|
| RUN28 (historique) | `08e998169c0dad9b` | 168 valeurs v1 et 224 valeurs v2 (bornes, plafonds et défauts critiques) **identiques** à la règle RUN29 |
| RUN29 (finale, F43–F53) | `4d6b306029f8745b` | idem |
