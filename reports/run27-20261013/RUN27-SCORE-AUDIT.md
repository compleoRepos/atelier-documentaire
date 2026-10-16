# RUN27 — Audit du calcul du score de confiance

> **Verdict de mesure (A) : la formule est reproductible, les bornes sont cohérentes et le plafond est dérivé — à une condition découverte pendant RUN27 : une mesure n’est comparable à une autre que si sa « règle » (code produit importé par la mesure) est identique.** Les scores publiés par RUN26 sont reproduits exactement avec la règle RUN26 ; ils ne sont pas remis en cause. Le seuil de 94/100 reste **mathématiquement inaccessible** sans références humaines (plafond de la borne basse : 76,8 par document, 75,8 pour le corpus).

Périmètre : code réel de `backend/app/documents/confidence_score.py` (v1, `doc-confidence-1`), `tools/recette/scorecard.py` (`scorecard-1`), `tools/recette/measure_v2.py` (`measure-v2.1-run18`), `tools/recette/render_outcome.py`, les artefacts privés des huit documents et les rapports RUN26. Chaque nombre de ce rapport est recalculé depuis les artefacts, jamais recopié depuis un rapport Markdown. Le calcul indépendant (`tools/recette/score_verify.py`) utilise des fractions exactes et ses propres tables de poids, déclarées séparément du moteur.

## 1. La contradiction 73,8 / 90,6 / 84,2 (RUN26, méthode v1)

### 1.1 Définitions exactes (identiques en v1 et v2)

Pour un document, chaque dimension *d* applicable a un poids *w_d* ; la somme des poids applicables est *A* ; le poids effectif est *e_d = 100 · w_d / A* (renormalisation). Chaque dimension est la moyenne de ses sous-composantes applicables ; une sous-composante inconnue vaut **0** dans la borne basse et **1** dans la borne haute.

- borne basse (score officiel) : *L = Σ e_d · min_d* ;
- borne haute : *H = Σ e_d · max_d* — **hypothèse** « toute inconnue serait parfaite », jamais un résultat ;
- points inconnus : *U = H − L* ;
- plafond structurel : *C = 100 − U* = meilleure borne basse atteignable si toutes les sous-composantes mesurées étaient parfaites et que les inconnues restaient inconnues.

### 1.2 Explication mathématique

Les trois nombres ne mesurent pas la même chose et ne se contredisent pas :

| Grandeur RUN26 (corpus) | Valeur exacte recalculée | Ce qu’elle borne |
| --- | --- | --- |
| Score officiel *L* | 73,7953 (affiché 73,8) | ce qui est prouvé |
| Borne haute *H* | 90,5662 (affiché 90,6) | hypothèse optimiste sur les inconnues |
| *U* moyen | 16,7708 | poids des inconnues |
| Plafond *C* moyen | **83,2292** (et non 84,2) | maximum atteignable par *L* |

- Identité vérifiée sur les 8 documents (et sur baseline, run24, run25, run26a) : *H − L = U = 100 − C*.
- Le plafond borne **la borne basse**, pas la borne haute : *H = L + U ≤ 100*. On a *H ≤ C* si et seulement si *L ≤ 100 − 2U*, soit *L ≤ 68,33* pour *U = 15,83*. En RUN26, seul DOC-005 (67,3) vérifiait *H < C*. **La prémisse « aucune borne haute ne doit dépasser 84,2 » est donc fausse** : une borne haute de 90,6 avec un plafond de 83,2 est cohérente.
- **Le 84,2 annoncé était lui-même faux.** `structural_ceiling()` (v1) utilisait une liste fixe d’inconnues et divisait par le nombre de sous-composantes de la spécification, en ignorant `NOT_APPLICABLE` et la renormalisation. Plafonds v1 réels : 84,167 pour sept documents, **76,667 pour DOC-003** (langue cible non applicable, dimension traduction entièrement inconnue) ; moyenne du corpus 83,229. Le test v1 était figé sur 84,2. Le défaut est documenté par le test `test_v1_ceiling_function_ignored_applicability_documented_regression` ; le module v1 est conservé à l’identique pour la reproductibilité.
- Corpus v1 : moyenne des scores **arrondis** des documents (effet −0,0078 point). La v2 calcule sur les valeurs exactes.

## 2. Effet de la dimension « preuves » (v1)

| Preuve v1 | run25 | run26 | Nature |
| --- | --- | --- | --- |
| `original_unchanged` | oui | oui | intégrité de la source, pas qualité de la traduction |
| `candidate_produced` | oui | oui | existence d’un PDF |
| `budget_respected` | oui | oui | conformité (32 768 tokens) |
| `block_provenance` | non | oui | traçabilité |
| `request_reconciliation` | non | oui | traçabilité |
| `generation_mode` | non | oui | traçabilité |
| `execution_journal` | non | oui | traçabilité |

- Les quatre preuves ajoutées par RUN26 **n’existaient pas avant RUN26** : elles attestent uniquement la traçabilité. Aucune ne démontre la qualité d’un document.
- Effet : 3/7 → 7/7, soit **+5,714 points sur chaque document**, y compris DOC-002, DOC-003, DOC-005 et DOC-006 dont le PDF est **identique au pixel près** entre run25e et run26b : pour ces quatre documents, 100 % du gain RUN26 vient des preuves.
- Ce gain augmente le score parce que la v1 traite la preuve comme 10 points de qualité. Ce poids n’est pas proportionné à une « confiance documentaire » : un document mal traduit mais bien tracé gagne autant qu’un document corrigé.
- Conformément à la consigne, la dimension n’est ni supprimée ni repondérée dans la v1 : les résultats historiques restent publiés et reproductibles. Une **version distincte** est proposée (§ 3).

## 3. Version 2 (`doc-confidence-2` / `scorecard-2`), gelée avant toute remédiation

Gel : 2026-10-13 08:11:36Z, empreintes SHA-256 de 8 fichiers (méthode, outil, vérificateur, tests), vérifiées avant chaque mesure. Le gel v1 RUN26 (4 fichiers) reste vérifié à l’identique.

1. **Les preuves deviennent une porte** : toutes exigées, sinon le document est `BLOCKED` (nombres affichés mais non opposables) ; elles n’ajoutent aucun point. Les sept dimensions de qualité gardent leurs poids v1 (somme 90, renormalisée).
2. **Plafond dérivé** de la formule et de l’applicabilité propre à chaque document (*C = 100 − U*), jamais codé en dur ; *U* est séparé entre « référence humaine manquante » et « mesure manquante ».
3. **Entités au-delà des chiffres** : alertes critiques d’entités du produit et une sous-composante humaine « noms, clauses et unités vérifiés » (aucun contrôle automatique ne les prouve). **Mise en page** : alertes critiques (débordement, masque excessif, texte sur l’encre, texte manquant, régions protégées), ignorées par la v1, dédupliquées par famille (le produit écrit certaines alertes en double : 34 lignes pour 17 débordements de DOC-004).
4. **Références humaines partielles** : intervalles (part validée *s*, exactitude *a* : basse *s·a*, haute *s·a + 1 − s*).
5. **Corpus** : poids égal par document attendu, valeurs exactes ; un document absent ou illisible est compté (basse 0, haute 100, `BLOCKED`), jamais ignoré.
6. **Affichage conservateur** : basses et plafonds arrondis vers le bas, hautes vers le haut ; le seuil est testé sur la valeur exacte (93,96 s’affiche 93,9, jamais 94,0).

`VALIDATED` exige une validation humaine autorisée, aucune sous-composante humaine inconnue, aucune mesure manquante, aucun défaut critique et aucun blocage.

## 4. Constat RUN27 : la règle de mesure avait bougé sous un gel intact

En recalculant les runs historiques avec le code RUN27, le score v1 de run26 passait de 73,8 à 71,9, alors que les 4 fichiers gelés v1 étaient intacts. Cause : `measure_v2.py` **recalcule les statuts de blocs avec des règles produit** qu’il importe (`block_status`, `typography`, `language_evidence`, `line_verification`, `pipeline`, détection de langue). Le correctif F33 (ponctuation répétée traitée comme typographie) a reclassé, **dans les runs historiques aussi**, deux blocs de DOC-005 : une ligne déjà en français, recopiée à la typographie près, ne compte plus comme « traduite ». Seul DOC-005 bouge, sur les deux méthodes.

Traitement :

- **Double mesure croisée** sur les mêmes artefacts : « règle RUN26 » (code de `c0a0629` dans un worktree propre, plus les seuls fichiers v2 gelés) et « règle RUN27 » (code final). Chaque comparaison de ce dossier est faite **à règle identique**.
- **Reproduction exacte** : avec la règle RUN26, la v1 redonne les valeurs publiées (63,1 / 67,9 / 68,0 / 73,8) et la v2 redonne son historique gelé à **0,0** près sur chaque document.
- **Correctif structurel** : `tools/recette/ruler_fingerprint.py` (`ruler-fingerprint-1`) hache la fermeture transitive des modules effectivement chargés par la mesure (29 fichiers produit, 5 fichiers d’outil). Deux mesures ne sont déclarées comparables que si leurs empreintes sont égales. Tests : fermeture transitive, modification produit seule détectée, présence des règles de statut et de typographie.

- Règle RUN26 : `311f7804c8b6ce76` ; règle RUN27 : `c6f0bb9a7b180eb6` (empreinte tronquée à 16 caractères).
- Fichiers produit de la fermeture de mesure modifiés par RUN27 :
  - `backend/app/ai/quality/engine.py`
  - `backend/app/ai/quality/entities.py`
  - `backend/app/ai/translation/service.py`
  - `backend/app/ai/translation/typography.py`
  - `backend/app/ai/vision/scorer.py`
  - `backend/app/documents/block_status.py`
  - `backend/app/documents/line_verification.py`
  - `backend/app/documents/ocr_recovery.py`

| Run | v2 — règle RUN27 : basse [haute] plafond | v2 — règle RUN26 pure | v1 — règle RUN27 | v1 — règle RUN26 | v1 publié RUN26 |
| --- | --- | --- | --- | --- | --- |
| baseline | 59,2 [86,5] C 72,7 | 59,2 [86,5] C 72,7 | 63,1 | 63,1 | 63,1 |
| run24 | 63,1 [87,4] C 75,8 | 64,6 [88,9] C 75,8 | 66,1 | 67,9 | 67,9 |
| run25 | 63,2 [87,5] C 75,8 | 64,6 [88,9] C 75,8 | 66,1 | 68,0 | 68,0 |
| run26 | 63,5 [87,8] C 75,8 | 64,9 [89,2] C 75,8 | 71,9 | 73,8 | 73,8 |
| run27 | 65,9 [90,2] C 75,8 | 67,2 [91,5] C 75,8 | 74,6 | 75,8 | — |

Lecture : à règle RUN27, la v2 passe de 63,5 à **65,9** (+2,4) ; à règle RUN26, de 64,9 à 67,2 (+2,3). La v1 gagne +2,7 (règle RUN27) ou +2,0 (règle RUN26). Le reclassement F33 est plus juste (une recopie FR→FR n’est pas une traduction), mais il ne doit jamais être présenté comme un progrès du document.

## 5. Gain RUN27 : une part provient d’un angle mort de la mesure

| Document | Couverture | Traduction | Fidélité source | Entités | Mise en page | OCR | Hallucination | Δ borne basse |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | +0,00 |
| DOC-002 | +5,58 | 0 | -0,20 | +0,93 | +0,05 | 0 | +0,03 | +6,39 |
| DOC-003 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | +0,00 |
| DOC-004 | +0,84 | -0,01 | 0 | 0 | +0,19 | 0 | -0,00 | +1,03 |
| DOC-005 | 0 | 0 | -0,03 | +8,33 | +2,22 | 0 | 0 | +10,53 |
| DOC-006 | 0 | 0 | 0 | +0,14 | +0,10 | 0 | 0 | +0,24 |
| DOC-007 | +0,68 | -0,01 | -0,01 | +0,08 | +0,22 | 0 | -0,00 | +0,96 |
| DOC-008 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | +0,00 |
| **Moyenne corpus** | +0,89 | -0,00 | -0,03 | +1,19 | +0,35 | +0,00 | +0,00 | +2,39 |

- DOC-005 : +10,53 point, dont **+8,33 sur les entités** (`digit_sequences` 0 → 1, `entity_alerts` 0,5 → 1). Ce gain est un **artefact** : la mesure compare les chiffres de la cible à la lecture OCR, elle-même fausse sur un identifiant (un chiffre lu comme une lettre). En run26, la cible était juste par hasard et la mesure la pénalisait ; en run27, la cible reproduit l’erreur d’OCR et la mesure la récompense. La régression est vérifiée visuellement sur l’original (défaut MV-01, critique, non détecté par les métriques).
- **Analyse de sensibilité, non officielle** : sans ces +8,33 points, DOC-005 serait à 49,9 (exact 49,97) et le corpus à 64,8 (exact 64,89 : +1,35 au lieu de +2,39). Le score officiel reste le résultat de la méthode gelée, publié avec cette réserve ; la méthode n’est pas modifiée après coup.
- DOC-002 (+6,39, dont +5,58 de couverture) correspond à un bloc réellement traduit et vérifié visuellement. DOC-004 (+1,03) et DOC-007 (+0,96) correspondent à des blocs réellement rendus, contrôlés sur planches. DOC-001, DOC-003 et DOC-008 : 0, PDF identiques ou changement imperceptible.

## 6. Verdict de mesure (A)

| Critère | Statut | Preuve |
| --- | --- | --- |
| Formule reproductible | **Oui, à règle identique** | replay v1 = publié RUN26 ; v2 historique reproduit à 0,0 ; empreinte de règle ajoutée |
| Bornes mathématiquement cohérentes | **Oui** | *H − L = U = 100 − C* à 10⁻¹⁴ près, 8/8 documents, 5 runs |
| Plafond justifié | **Oui (v2) ; faux en v1** | dérivé de l’applicabilité : 76,85 (7 documents), 68,52 (DOC-003), corpus 75,81 |
| Scores recalculables | **Oui** | `score_verify.py` (fractions exactes), écart v2 ≤ 1,4·10⁻¹⁴ ; voir RUN27-SCORE-MATHEMATICAL-VERIFICATION.md |
| Inconnues explicites | **Oui** | 4 sous-composantes humaines inconnues par document, motif `HUMAN_REFERENCE_MISSING`, jamais positives |
| Tests du calculateur | **Oui** | 17 tests v2 + 9 v1 ; 5 mutations du moteur toutes détectées |
| Défaut critique masqué par une moyenne élevée | **Impossible** | statut `REVIEW_REQUIRED` dès un défaut critique ; test dédié |
| Limite connue | **Angle mort** | les entités sont comparées à l’OCR, pas à l’image : MV-01 invisible (voir RUN27-OPEN-ISSUES.md) |
