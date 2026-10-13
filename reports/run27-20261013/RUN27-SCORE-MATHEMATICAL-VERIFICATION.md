# RUN27 — Vérification mathématique du score

Toutes les valeurs ci-dessous sont **générées par script** depuis les exports anonymisés `documents/DOC-00x.json` et `documents/corpus.json` (précision 10⁻¹²), eux-mêmes produits par `tools/recette/scorecard_v2.py` (`scorecard-2`, méthode `doc-confidence-2` gelée) sur les artefacts du run verdict **run27b**, **règle de mesure RUN27**. Aucun nombre n’est recopié à la main.

## 1. Formule exacte (`doc-confidence-2`)

1. Sous-composante : valeur mesurée dans [0, 1], **inconnue** (motif `HUMAN_REFERENCE_MISSING` ou `MEASUREMENT_MISSING`) ou `NOT_APPLICABLE`. Une inconnue vaut **0 en borne basse et 1 en borne haute** ; une sous-composante non applicable est retirée de sa dimension.
2. Dimension : `min_d` = moyenne des bornes basses de ses sous-composantes applicables, `max_d` = moyenne de leurs bornes hautes. Une dimension sans sous-composante applicable est non applicable.
3. Poids : couverture 20, traduction 15, fidélité source 10, entités 15, mise en page 10, OCR 10, hallucination 10 (somme 90, proportions v1). Poids applicable *A* = somme des poids des dimensions applicables ; poids effectif *e_d = 100 · w_d / A*.
4. Document : *L = Σ e_d · min_d* (score officiel), *H = Σ e_d · max_d*, *U = H − L*, plafond *C = 100 − U*.
5. Porte de preuves : les 7 preuves exigées (original inchangé, provenance par bloc, rapprochement des requêtes, mode de génération, journal, PDF produit, budget) ; une preuve manquante → `BLOCKED`, sans ajouter ni retirer de point.
6. Statut : `VALIDATED` si et seulement si *L ≥ 94* (valeur exacte) **et** 0 défaut critique **et** 0 inconnue humaine **et** 0 mesure manquante **et** validation humaine autorisée **et** non bloqué ; sinon `REVIEW_REQUIRED` (ou `BLOCKED`).
7. Corpus : *L_c = (1/N) Σ L_i* sur les *N* = 8 documents **attendus**, valeurs exactes ; un document absent compte pour *L = 0, H = 100*.
8. Affichage : *L* et *C* arrondis vers le bas au dixième, *H* vers le haut.

## 2. Exemple entièrement recalculable : DOC-005 (run27)

| Dimension | Poids | Poids effectif = poids × 100 / 90 | Sous-composantes (borne basse) | min | max | Contribution basse | Contribution haute |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Couverture | 20 | 22,2222 | written_share = 0,213 | 0,2131 | 0,2131 | 4,7356 | 4,7356 |
| Traduction | 15 | 16,6667 | semantic_accuracy = inconnue (HUMAN_REFERENCE_MISSING); target_language = 1,000 | 0,5000 | 1,0000 | 8,3333 | 16,6667 |
| Fidélité source | 10 | 11,1111 | pages_preserved = 1,000; regions_unaltered = 0,984 | 0,9921 | 0,9921 | 11,0229 | 11,0229 |
| Entités | 15 | 16,6667 | digit_sequences = 1,000; entity_alerts = 1,000; names_clauses_verified = inconnue (HUMAN_REFERENCE_MISSING) | 0,6667 | 1,0000 | 11,1111 | 16,6667 |
| Mise en page | 10 | 11,1111 | in_page = 1,000; no_collision = 1,000; no_critical_layout_alert = 1,000; no_text_over_ink = 1,000; not_truncated = 1,000 | 1,0000 | 1,0000 | 11,1111 | 11,1111 |
| OCR | 10 | 11,1111 | character_accuracy = inconnue (HUMAN_REFERENCE_MISSING); engine_confidence = 0,825 | 0,4126 | 0,9126 | 4,5841 | 10,1396 |
| Hallucination | 10 | 11,1111 | no_length_anomaly = 1,000; no_unreliable_source_translated = 1,000; proven_by_reference = inconnue (HUMAN_REFERENCE_MISSING) | 0,6667 | 1,0000 | 7,4074 | 11,1111 |
| **Total** | 90 | 100 |  |  |  | **58,3055** | **81,4537** |

Contrôle : *L = 58,3055* et *H = 81,4537* sont exactement les valeurs stockées par le moteur. *U = 23,1481 = 16,6667 × ½ (traduction) + 16,6667 × ⅓ (entités) + 11,1111 × ½ (OCR) + 11,1111 × ⅓ (hallucination)*, soit les quatre sous-composantes humaines inconnues ; *C = 100 − 23,1481 = 76,8519*. Une sous-composante non mesurée ne rapporte **aucun** point à la borne basse.

## 3. Identités sur les huit documents (run27)

| Document | Poids applicable | Basse exacte | Haute exacte | U = haute − basse | Plafond C exact | |U − (100 − C)| | Affiché basse / haute / plafond |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 90 | 63,1569 | 86,3050 | 23,1481 | 76,8519 | 0.0e+00 | 63,1 / 86,4 / 76,8 |
| DOC-002 | 90 | 66,7078 | 89,8560 | 23,1481 | 76,8519 | 0.0e+00 | 66,7 / 89,9 / 76,8 |
| DOC-003 | 90 | 62,7058 | 94,1873 | 31,4815 | 68,5185 | 7.1e-15 | 62,7 / 94,2 / 68,5 |
| DOC-004 | 90 | 66,2232 | 89,3714 | 23,1481 | 76,8519 | 0.0e+00 | 66,2 / 89,4 / 76,8 |
| DOC-005 | 90 | 58,3055 | 81,4537 | 23,1481 | 76,8519 | 0.0e+00 | 58,3 / 81,5 / 76,8 |
| DOC-006 | 90 | 73,4976 | 96,6458 | 23,1481 | 76,8519 | 0.0e+00 | 73,4 / 96,7 / 76,8 |
| DOC-007 | 90 | 70,3971 | 93,5453 | 23,1481 | 76,8519 | 0.0e+00 | 70,3 / 93,6 / 76,8 |
| DOC-008 | 90 | 66,4927 | 89,6408 | 23,1481 | 76,8519 | 0.0e+00 | 66,4 / 89,7 / 76,8 |

- *|U − (100 − C)|* ≤ 7,1·10⁻¹⁵ : identité exacte aux erreurs d’arrondi binaire près.
- DOC-003 : la sous-composante « langue cible » est non applicable (aucun texte à traduire évaluable) ; la dimension traduction ne garde que la référence humaine, d’où *U* = 31,48 et un plafond de 68,5.
- Aucune mesure manquante (`MEASUREMENT_MISSING` = 0 point sur les 8 documents) : toute l’incertitude restante vient des références humaines absentes.

| Document | Points inconnus (réf. humaine) | Points inconnus (mesure) | Sous-composantes inconnues | Non applicables |
| --- | --- | --- | --- | --- |
| DOC-001 | 23,1481 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | — |
| DOC-002 | 23,1481 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | — |
| DOC-003 | 31,4815 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | translation.target_language |
| DOC-004 | 23,1481 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | — |
| DOC-005 | 23,1481 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | — |
| DOC-006 | 23,1481 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | — |
| DOC-007 | 23,1481 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | — |
| DOC-008 | 23,1481 | 0,0000 | entities.names_clauses_verified, hallucination.proven_by_reference, ocr.character_accuracy, translation.semantic_accuracy | — |

## 4. Dimensions par document (run27, borne basse–borne haute)

| Document | Couverture | Traduction | Fidélité source | Entités | Mise en page | OCR | Hallucination |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 0,588 | 0,418–0,918 | 0,750 | 0,667–1,000 | 0,982 | 0,483–0,983 | 0,667–1,000 |
| DOC-002 | 0,644 | 0,500–1,000 | 0,951 | 0,667–1,000 | 0,960 | 0,395–0,895 | 0,660–0,993 |
| DOC-003 | 0,741 | 0,000–1,000 | 0,995 | 0,667–1,000 | 1,000 | 0,500–1,000 | 0,667–1,000 |
| DOC-004 | 0,618 | 0,489–0,989 | 0,998 | 0,667–1,000 | 0,928 | 0,401–0,901 | 0,665–0,998 |
| DOC-005 | 0,213 | 0,500–1,000 | 0,992 | 0,667–1,000 | 1,000 | 0,413–0,913 | 0,667–1,000 |
| DOC-006 | 0,937 | 0,500–1,000 | 0,842 | 0,667–1,000 | 0,991 | 0,493–0,993 | 0,666–0,999 |
| DOC-007 | 0,796 | 0,490–0,990 | 0,998 | 0,667–1,000 | 0,965 | 0,380–0,880 | 0,666–0,999 |
| DOC-008 | 0,591 | 0,500–1,000 | 0,949 | 0,667–1,000 | 0,962 | 0,476–0,976 | 0,667–1,000 |

## 5. Corpus

| Run | v2 — règle RUN27 : basse [haute] plafond | v2 — règle RUN26 pure | v1 — règle RUN27 | v1 — règle RUN26 | v1 publié RUN26 |
| --- | --- | --- | --- | --- | --- |
| baseline | 59,2 [86,5] C 72,7 | 59,2 [86,5] C 72,7 | 63,1 | 63,1 | 63,1 |
| run24 | 63,1 [87,4] C 75,8 | 64,6 [88,9] C 75,8 | 66,1 | 67,9 | 67,9 |
| run25 | 63,2 [87,5] C 75,8 | 64,6 [88,9] C 75,8 | 66,1 | 68,0 | 68,0 |
| run26 | 63,5 [87,8] C 75,8 | 64,9 [89,2] C 75,8 | 71,9 | 73,8 | 73,8 |
| run27 | 65,9 [90,2] C 75,8 | 67,2 [91,5] C 75,8 | 74,6 | 75,8 | — |

- Corpus run27 (règle RUN27) : moyenne exacte des huit *L* du § 3 = **65,9358**, affichée 65,9 ; borne haute 90,1257, affichée 90,2 ; plafond 75,8102 (sept plafonds de 76,8519 et un de 68,5185, divisés par 8).
- Le seuil 94 est inaccessible tant que les références humaines manquent : 94 > 75,81. Même avec des mesures automatiques parfaites, la borne basse ne peut dépasser le plafond.

## 6. Vérification indépendante

`tools/recette/score_verify.py` recalcule chaque document avec des fractions exactes (`fractions.Fraction`) et **ses propres tables de poids**, déclarées séparément du moteur, puis compare avec le JSON produit par `scorecard_v2.py`.

| Contrôle | Résultat |
| --- | --- |
| Écart maximal v2, document (run27, règle RUN27) | ≤ 1,4·10⁻¹⁴ |
| Écart maximal v2, corpus | ≤ 1,4·10⁻¹⁴ |
| v2 règle RUN26 pure : historique gelé reproduit | 0,0 sur chaque document (baseline, run24, run25, run26) |
| v1 règle RUN26 : valeurs publiées RUN26 | 63,1 / 67,9 / 68,0 / 73,8 reproduites |
| v1 (règle RUN27), écart document | ≤ 4,98·10⁻² (la v1 stocke des dimensions arrondies à 10⁻⁶ et un corpus de scores arrondis : défaut v1 documenté, corrigé en v2) |
| Identités *H − L = U = 100 − C* | vérifiées sur chaque document de chaque run |
| Score falsifié dans le JSON | détecté (test `test_verifier_detects_a_tampered_score`) |

## 7. Cas de test obligatoires du calculateur

| Cas exigé | Test (`backend/tests/unit/test_confidence_score_v2.py`) |
| --- | --- |
| Document entièrement mesuré | `test_all_measured_and_perfect`, `test_all_measured_with_zero_values` |
| Document partiellement inconnu | `test_partially_unknown_dimension_and_partially_validated_interval` |
| Dimension entièrement non applicable | `test_entirely_not_applicable_dimension_is_renormalised` |
| Dimension partiellement inconnue | `test_partially_unknown_dimension_and_partially_validated_interval` |
| Défaut critique avec score numérique élevé | `test_critical_defect_with_high_numeric_score_never_passes` |
| Preuve manquante | `test_missing_evidence_blocks_without_adding_or_removing_points` |
| Référence humaine partiellement validée | `test_partially_unknown_dimension_and_partially_validated_interval` |
| Document absent ou illisible | `test_absent_or_unreadable_document_is_counted_never_dropped` |
| Corpus de documents de tailles différentes | `test_documents_of_different_sizes_have_equal_weight` |
| Bornes égales lorsque tout est mesuré | `test_all_measured_and_perfect`, `test_bounds_identities_hold_on_random_documents` |
| Plafond atteint | `test_structural_ceiling_is_reached_and_derived_from_applicability` |
| Inconnues jamais positives | `test_unknowns_are_never_positive_and_are_qualified` |
| Arrondi qui ne fait pas franchir le seuil | `test_conservative_display_never_shows_a_threshold_that_is_not_met` |
| Preuves = porte, poids v1 conservés | `test_evidence_is_a_gate_and_quality_weights_keep_v1_proportions` |
| Défaut du plafond v1 documenté | `test_v1_ceiling_function_ignored_applicability_documented_regression` |
| Vérificateur indépendant | `test_verifier_detects_a_tampered_score`, `test_v1_verifier_identities_on_a_v1_result` |
| Alertes de mise en page dédupliquées | `test_layout_alert_families_are_deduplicated` |

17 tests v2 et 9 tests v1 : tous passent (voir RUN27-REGRESSION-RESULTS.md).

## 8. Contre-épreuves par mutation (copies temporaires hors dépôt)

| Mutation du moteur v2 | Tests en échec |
| --- | --- |
| M1 — arrondi au plus proche au lieu de l’arrondi conservateur | 2 |
| M2 — porte de preuves supprimée (une preuve manquante ne bloque plus) | 1 |
| M3 — une inconnue comptée positivement dans la borne basse | 4 |
| M4 — document absent ignoré dans le corpus | 1 |
| M5 — défaut critique ignoré par le statut | 1 |

Les 5 mutations sont détectées. Le moteur réel est rétabli et identique au fichier gelé (empreinte vérifiée).
