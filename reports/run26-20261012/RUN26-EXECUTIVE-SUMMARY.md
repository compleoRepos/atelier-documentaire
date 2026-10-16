# RUN26 — Synthèse

> **Verdict : seuil de 94/100 NON atteint.** Score officiel du corpus : **73,8/100** (borne basse), contre **68,0**
> au RUN25. La borne haute, qui suppose bonnes toutes les valeurs inconnues, est 90,6.
> Aucun document n'atteint le seuil. **7 documents sur 8** ont encore des défauts critiques.
> Les **8 documents** sont `REVIEW_REQUIRED`. **Aucune validation humaine** n'a été réalisée.
> **La validation humaine et la mise en production restent bloquées.**

## 1. Ce que dit le score

| Indicateur | RUN25 (run25e) | RUN26 (verdict) |
|---|---|---|
| Score officiel du corpus (borne basse) | 68,0 | **73,8** |
| Borne haute (inconnues comptées bonnes) | 84,8 | 90,6 |
| Documents au seuil (≥ 94 et 0 défaut critique) | 0 / 8 | **0 / 8** |
| Documents avec défaut critique | 7 / 8 | 7 / 8 |
| Alertes critiques émises par le produit (occurrences, corpus) | 105 | 104 |
| Défauts critiques bloquants selon le scorecard (alertes produit + contrôles du scorecard) | 106 | 105 |
| Couverture écrite du corpus (écrits / attendus) | 0,8419 | 0,8381 |
| Statut | `REVIEW_REQUIRED` ×8 | `REVIEW_REQUIRED` ×8 |

Le gain de 5,8 points vient **presque entièrement de la complétude des preuves**, soit +5,71 points. RUN26 trace
désormais chaque bloc et chaque requête, et rapproche ces traces des requêtes réellement envoyées. Les autres
dimensions bougent de moins de 0,1 point. **RUN26 n'a donc pas amélioré de façon mesurable la qualité de
traduction.** Il a rendu le résultat plus vérifiable et plus prudent.

| Dimension (poids) | run25e (points) | run26 (points) | Δ (points) |
|---|---|---|---|
| Couverture (20) | 12,64 | 12,62 | -0,02 |
| Traduction (15) | 6,36 | 6,37 | +0,01 |
| Fidélité source (10) | 9,37 | 9,37 | +0,00 |
| Entités (15) | 14,38 | 14,38 | +0,00 |
| Mise en page (10) | 9,99 | 9,99 | -0,00 |
| OCR (10) | 4,39 | 4,42 | +0,04 |
| Hallucination (10) | 6,58 | 6,65 | +0,07 |
| Preuves (10) | 4,29 | 10,00 | +5,71 |
| **Total (score officiel)** | **67,99** | **73,80** | **+5,81** |

La couverture écrite du corpus baisse légèrement, de 0,8419 à 0,8381. C'est un choix assumé : la correction F25
n'envoie plus en traduction automatique un texte OCR non fiable. Ce texte part en revue humaine (statut
`UNCERTAIN`). Ce n'est pas présenté comme un progrès de couverture.

## 2. Pourquoi 94 est hors d'atteinte aujourd'hui

1. **Plafond structurel de 84,2.** Sans traductions de référence, sans transcription humaine des scans et sans revue
   humaine des ajouts et omissions, trois sous-composantes restent inconnues. La méthode les compte 0 dans le score
   officiel, ce qui interdit de dépasser 84,2/100, même pour un document parfait par ailleurs (voir
   [la méthodologie](RUN26-SCORE-METHODOLOGY.md), §5). Ce plafond est voulu : le prompt interdit de transformer des
   inconnues en résultats positifs.
2. **Défauts critiques.** Même au-dessus de 94, un document avec un défaut critique reste sous le seuil. Le corpus en
   compte 105 : 104 alertes critiques du produit (débordements, encre source sous la traduction, entités modifiées,
   régions protégées altérées, masques trop larges, textes absents du rendu), plus 1 écart de chiffres que seul le
   scorecard détecte (DOC-005). Le produit ne le voit pas : c'est un défaut ouvert.
3. **Couverture.** Plusieurs documents n'ont qu'une faible part de texte réellement écrite dans le PDF : DOC-002
   0,393 ; DOC-005 0,454 ; DOC-004 0,580 ; DOC-001 0,588 ; DOC-008 0,591.

## 3. Ce qui a été fait

| Étape | Résultat |
|---|---|
| Audit RUN25 | Divergence entre les deux tableaux RUN25 expliquée : un état intermédiaire (run25c) et le verdict (run25e). Les rapports RUN25 versionnés citent bien le verdict. Une source de vérité unique a été établie (mesure v2.1 + scorecard) |
| P0 preuves | Trace par requête : identifiant de corrélation, identifiant de réponse validé, horodatages, statut HTTP. Provenance déclarée pour chaque bloc. Mode de génération explicite. Journal JSONL horodaté avec empreinte du code et HEAD Git |
| Score | Score de confiance documentaire en 8 dimensions, avec bornes basse et haute. Méthode **gelée avant les correctifs** et recontrôlée (4/4) à chaque étape |
| F25 | Relecture OCR prudente sur copie prétraitée. 16 lignes récupérées et 4 confirmées. 79 blocs non récupérés envoyés en revue humaine, au lieu d'être traduits à l'aveugle |
| F26 | Vérification après rendu : un bloc n'est `TRANSLATED` que si sa cible est relue dans le PDF. 487 placements sur 487 vérifiés |
| F27 | Les alertes de rendu tiennent compte de F26. Le compteur interne de textes traduits « manquants » passe de 65 à 44 : il y avait 21 faux positifs |
| F28 | Un identifiant ou un nombre réécrit suit le chemin normal, au lieu d'être compté « préservé » |
| Corpus | Run intermédiaire : 5 appels Interim sur 4 documents, réservation maximale de 17 379 tokens (≤ 32 768), 0 violation. Run de verdict : rejoue la mémoire de traduction du run intermédiaire, 0 nouvelle requête, déclaré `TRANSLATION_MEMORY_REUSE_ONLY` |

## 4. Tableau récapitulatif

| Document | Score avant (run25e) | Score après (run26) | Couverture écrite (run25e → run26) | Défauts critiques (run26, occurrences) | Statut |
|---|---|---|---|---|---|
| DOC-001 | 65,8 [81,6] | **72,0** [87,9] | 0,576 → 0,588 | `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 | `REVIEW_REQUIRED` |
| DOC-002 | 64,8 [80,7] | **70,6** [86,4] | 0,393 → 0,393 | `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 | `REVIEW_REQUIRED` |
| DOC-003 | 65,7 [89,1] | **71,4** [94,8] | 0,741 → 0,741 | aucun | `REVIEW_REQUIRED` |
| DOC-004 | 68,6 [84,4] | **74,5** [90,4] | 0,589 → 0,580 | `LAYOUT_OVERFLOW` ×17, `PROTECTED_REGION_CHANGED` ×6, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `VISUAL_MASK_TOO_LARGE` ×1 | `REVIEW_REQUIRED` |
| DOC-005 | 61,6 [77,4] | **67,3** [83,1] | 0,454 → 0,454 | `ENTITY_DIGITS_MISMATCH` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 | `REVIEW_REQUIRED` |
| DOC-006 | 75,5 [91,3] | **81,2** [97,0] | 0,937 → 0,937 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1, `HALLUCINATION_UNIT_CHANGED` ×1, `LAYOUT_OVERFLOW` ×3, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×12, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1, `VISUAL_MASK_TOO_LARGE` ×12 | `REVIEW_REQUIRED` |
| DOC-007 | 72,5 [88,3] | **78,1** [93,9] | 0,778 → 0,766 | `LAYOUT_OVERFLOW` ×7, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×2, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×4, `UNMAPPED_TABLE_CONTENT` ×1, `VISUAL_MASK_TOO_LARGE` ×2 | `REVIEW_REQUIRED` |
| DOC-008 | 69,4 [85,3] | **75,2** [91,1] | 0,591 → 0,591 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 | `REVIEW_REQUIRED` |
| **Corpus** | **68,0** [84,8] | **73,8** [90,6] | 0,8419 → 0,8381 | 7 documents sur 8 | `REVIEW_REQUIRED` ×8 |

Notes :

- Les scores sont des **bornes basses** ; la borne haute est entre crochets.
- Défauts critiques : les **occurrences** d'alertes de sévérité `critical`, par code. Les trois codes `RENDER_*`
  présents dans 7 documents correspondent à **une seule** mesure de rendu, signalée sous trois codes.
- Le score officiel de DOC-003 est sous le seuil (71,4), même s'il n'a aucun défaut critique et que sa borne haute
  (94,8) le dépasse.

## 5. Tests réellement exécutés

| Contrôle | Résultat |
|---|---|
| Backend, périmètre exact de la CI (unit, intégration, e2e, régression, sécurité), code final | **659 passed**, 0 failed, 0 error, 0 skipped, 69 warnings, 210,4 s |
| Même suite sur le code du run de verdict (`449b3ab80ed0b263`) | 646 passed, 0 failed (avant ajout des 13 tests P0) |
| Golden dataset (8 documents) | code du run de verdict : **8 passed**, 0 failed, 1 176,5 s ; code final : **8 passed**, 0 failed, 1 153,8 s |
| Tests ciblés RUN26 | 49 passed : F25 à F28 (27), traçabilité P0 (13), score (9) |
| Contre-épreuves (correctif retiré, le test doit échouer) | F25 : 5 échecs ; F27/F28 : 4 ; P0 : 8 + 3 |
| `ruff check backend tools` (commande de la CI) | OK |
| Frontend : `npm ci`, typecheck, tests, build | OK — 6 fichiers, **16 tests passed** |
| `npm audit --audit-level=high` | 0 vulnérabilité |
| `pip-audit -r backend/requirements.txt --strict` | aucune vulnérabilité connue |
| Audit anti-fuite (dépôt entier comparé au corpus privé) | fuites anciennes trouvées et retirées de l'arbre ; historique Git non réécrit (voir défauts ouverts, OI-24) |
| CI GitHub (commit `b61f25a`, PR brouillon #4) | **success** : frontend, backend, intégration et migrations, conteneurs et manifestes ; portes privée et de publication *skipped* par conception (voir [résultats de régression](RUN26-REGRESSION-RESULTS.md), §7) |

## 6. Ce qui n'est pas prouvé

- **Qwen n'a pas été testé.** Aucun appel réel à Qwen/vLLM n'a eu lieu. Interim (gpt-5-mini) reste le moteur temporaire
  de développement. Son usage est tracé et borné à 32 768 tokens.
- **Aucune référence humaine** n'existe. L'exactitude sémantique, l'exactitude OCR et l'absence d'hallucination
  prouvée restent inconnues.
- Les noms, clauses et données bancaires ne sont contrôlés automatiquement que pour leurs **nombres**.

## 7. Pour aller plus loin

Corrections et étapes nécessaires, sans promesse de résultat : voir [défauts ouverts](RUN26-OPEN-ISSUES.md).

1. Faire valider par un humain autorisé des traductions et des transcriptions de référence pour les 8 documents.
   C'est la seule voie pour lever le plafond de 84,2.
2. Corriger les causes des 105 défauts critiques : débordements (29), masques trop larges (15 + 15), encre résiduelle
   (10), textes absents du rendu (7 × 3 codes), régions protégées (6), entités (8), contenu de tableau non apparié (1).
3. Traiter les 102 blocs `model_returned_source` et les 146 blocs `UNCERTAIN`.

Détails : [avant/après](RUN26-BEFORE-AFTER.md), [causes racines](RUN26-ROOT-CAUSES.md),
[régressions](RUN26-REGRESSION-RESULTS.md), [défauts ouverts](RUN26-OPEN-ISSUES.md), [JSON par document](documents/).
