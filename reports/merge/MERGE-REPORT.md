# Rapport de merge — Prompt 1 (industrialisation) + Prompt 2 (fidélité)

Date : 2026-10-08. Auteur et committer : Hamza NORDINE. Base commune : `6fb913a`.

| Branche | Commit final | Statut déclaré |
|---|---|---|
| `feature/prompt-1-industrialisation-20261008` | `0016589` (code `b7e40a0`) | completed, CI 37760420819 success |
| `feature/prompt-2-fidelite-20261008` | `154691d` | completed |
| `integration/prompt-1-2-20261008` | commit de merge (ce rapport) | recette post-merge ci-dessous |

## 1. Conflits Git résolus

Seul `backend/app/documents/pipeline.py` était en conflit (4 zones). Les deux apports ont été conservés, sans en abandonner aucun.

| Zone | Prompt 1 conservé | Prompt 2 conservé | Résolution |
|---|---|---|---|
| `_tables` | Conversion des bbox raster → coordonnées source (points PDF) | `enrich_tables` (fond, bordures, cellules) | Conversion **puis** enrichissement, sur les coordonnées source uniquement |
| Analyse DOCX | `source_sha256`, `source_metadata`, contrôle d'immuabilité | `protect_ir` (régions visuelles DOCX) | `protect_ir` puis provenance et contrôle SHA |
| IR PDF/image | Schéma v3 : preprocessing, candidats visuels, timings, classifieur | `protect_ir` (visuels PDF + annotations) | IR P1, puis fusion P2 des régions, puis contrôle SHA strict |
| Reconstruction PDF | Adaptateur TIFF → copie PDF sans perte (`raster_adapter`) | Renderer dédié `pdf_fidelity.render_pdf` (cellules, masques, géométrie) | Renderer P2 ; un TIFF lui est transmis via l'adaptateur P1, en pixels source |

## 2. Défauts d'intégration détectés par la recette et corrigés

Ces défauts n'existaient dans aucune branche prise isolément. Ils n'apparaissent qu'une fois les deux branches combinées.

| # | Défaut constaté | Effet | Correctif | Test ajouté |
|---|---|---|---|---|
| 1 | Sur un PDF natif, le détecteur raster P1 classait le cadre coloré d'un tableau comme « cachet/logo » | Tableau entier protégé, donc non traduit (`changed_blocks=0`) | `_exclude_table_art` : un candidat automatique dont l'IoU avec un tableau détecté est ≥ 0,6 n'est plus protégé, avec l'avertissement tracé `PROTECTED_CANDIDATE_TABLE_ART` (bbox conservée). Un visuel qui ne chevauche le tableau qu'en partie reste protégé | `test_merge_prompt1_prompt2.py` (4 tests) |
| 2 | Les candidats automatiques P1 recevaient la provenance par défaut `user_annotation_unvalidated` | Traçabilité fausse : une détection présentée comme une annotation humaine | `_clip_candidate_regions` : provenance `automatic_candidate:preprocessing`, bornage aux limites de page, rejet tracé des candidats dégénérés ou invalides. Les annotations utilisateur restent fail-closed | idem |
| 3 | P2 renommait le type de région en `protected_visual` | Divergence avec le cahier des charges (§18) et le modèle Angular (`protected_visual_region`) | Type unifié `protected_visual_region` (PDF et DOCX) | assertion de schéma dans le test de merge |
| 4 | Recherche de rectangles raster en O(G⁴) en Python (`layout._raster_segments`), alimentée par le raster 2× de P1 | Point chaud CPU confirmé par profilage (`present()`) | Algorithme **strictement équivalent** (même prédicat, mêmes rectangles, même ordre) : arêtes verticales filtrées une fois par paire horizontale, cache des tests horizontaux, arrêt anticipé au-delà de 80 px, index vectorisé. Une borne de travail explicite (`_MAX_RASTER_PRESENCE_CHECKS`) produit `RASTER_RECTANGLE_LIMIT_REQUIRES_REVIEW` au lieu d'une couverture tronquée silencieuse | `test_raster_rectangles_merge.py` (3 tests : oracle exhaustif, page dense bornée, limite signalée) |

### Banc d'équivalence ancien/nouvel algorithme (preuves locales, aucune donnée affichée)

| Jeu | Cas | Résultats identiques | Différences | Ancien total | Nouveau total | Pire page (ancien → nouveau) |
|---|---|---|---|---|---|---|
| Images synthétiques aléatoires | 40 | 40 | 0 | — | max 0,03 s | — |
| Pages traitées comme scans (8 PDF réels) | 31 | 31 | 0 | 1 014,2 s | 28,3 s | 81,6 s → 2,2 s |

Sur 29 des 31 pages, la recherche atteint le plafond existant de 4 096 rectangles, **avec l'ancien comme avec le nouvel algorithme**. Ces pages portent déjà l'incertitude `RASTER_RECTANGLE_LIMIT_REQUIRES_REVIEW` et doivent être revues : c'est une limite connue, pas une régression.

## 3. Recette post-merge (worktree d'intégration, environnement Python isolé)

| Contrôle | Résultat |
|---|---|
| Ruff (backend + tools) | OK |
| Suite technique Python (unit, integration, e2e, regression, security) | **360 passed, 0 failed, 0 skipped** (195,6 s) |
| Golden Tests techniques sur les 8 documents réels (31 pages, OCR local, aucun appel à un modèle) | **8 passed / 8** (985,7 s) |
| SHA256 des 8 originaux avant/après | Inchangés |
| pip-audit `--strict` | No known vulnerabilities found |
| Angular (typecheck, 16 tests, build, npm audit) sur les sources fusionnées | OK, 16 passed, 0 vulnérabilité |

Durées par document après merge : DOC-001 44,5 s · DOC-002 28,3 s · DOC-003 22,7 s · DOC-004 108,1 s · DOC-005 74,5 s · DOC-006 451,6 s · DOC-007 198,4 s (305,5 s avant le correctif n°4) · DOC-008 57,4 s.

## 4. Ce qui reste hors périmètre vérifiable (inchangé, non masqué)

| Exigence | Statut |
|---|---|
| Traduction modèle des 8 documents réels | NOT_EXECUTED — décision de confidentialité : Interim est autorisé uniquement sur des données synthétiques |
| Endpoint, poids et tokenizer Qwen privés (32K réel) | NOT_AVAILABLE_IN_ENVIRONMENT |
| Mode Interim temporaire | Synthétique uniquement ; 22 000 tokens d'entrée + 8 000 de génération totale (`max_completion_tokens`, raisonnement inclus) + 2 768 de marge = 32 768 ; refusé en production/private |
| Références humaines Golden, baseline qualité bancaire | NOT_AVAILABLE ; scores linguistiques et sémantiques maintenus à `null` |
| Authentification des signatures et cachets | Non réalisée : les régions protégées sont des candidats à revoir |
| Qualification sur infrastructure bancaire / AWS | Non réalisée : aucun accès AWS configuré dans l'environnement |

Qualification bancaire : **NON VALIDÉE**. Le merge est techniquement recetté, mais il ne vaut pas certification.
