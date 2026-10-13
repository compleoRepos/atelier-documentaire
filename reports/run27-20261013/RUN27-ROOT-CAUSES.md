# RUN27 — Causes racines et correctifs

Méthode : chaque défaut critique RUN26 a été **reproduit** sur les artefacts privés (identifiants de blocs, séquences de chiffres, géométrie, sans texte dans ce rapport). Il a été corrigé à la source quand une cause générique existait, couvert par un **test synthétique** (aucune donnée réelle), contre-éprouvé par **mutation**, puis **rejoué** sur les huit documents et contrôlé sur les **PDF** (planches privées). Une alerte n’a jamais été supprimée pour améliorer un compteur. Quand une alerte disparaît parce que la mesure était fausse, c’est dit explicitement (F32).

## 1. Entités (P0) — F29

| Réf. | Reproduction (run26b) | Cause racine | Correctif | Effet mesuré corpus |
| --- | --- | --- | --- | --- |
| F29 A | DOC-002 p001-b0017, DOC-006 p007-b0035 : traductions refusées par la garde (`entity_guard_rejected`), cible = source | l’expression des nombres protégés exigeait une non-lettre après le nombre : un nombre **collé à une lettre** (montant suivi d’une devise, ordinal anglais) n’était ni protégé ni compté côté source, mais l’était côté cible → faux écart → rejet d’une traduction correcte | protection des nombres collés (fin de nombre = fin de chiffres) ; contrôle d’intégrité **symétrique** sur toutes les suites de chiffres | DOC-002 : bloc traduit, chiffres identiques, contrôlé sur le PDF ; DOC-006 : voir F34 |
| F29 A (suite) | DOC-005 p002-b0033 : un chiffre **inventé** par le modèle n’était pas détecté par le produit (seul le scorecard le voyait) | même asymétrie | même contrôle symétrique | chiffre inventé désormais refusé ; voir MV-01 pour la régression qui suit |
| F29 B | DOC-007 p001-b0082 : source OCR très bruitée (mots déformés), traduite puis refusée par la garde | aucune porte de plausibilité lexicale au-dessus du seuil F25 (0,60) | porte `lexically_implausible` : écriture latine ≥ 90 %, ≥ 8 mots, langue du bloc détectée et présente dans le lexique, part de mots connus < 0,70 → `UNCERTAIN`, original conservé, revue humaine | 4 blocs passent en revue (DOC-004 1, DOC-007 3) ; aucun autre bloc touché ; l’arabe et les langues sans lexique sont exclus par construction |
| F29 C | DOC-006 : `HALLUCINATION_UNIT_CHANGED` (2 unités « m » perdues) | la table d’unités ne reconnaissait pas la forme française accentuée (« mètres ») : faux positif vérifié à la source | formes françaises accentuées et formes it/es/nl/de des unités | 1 seul bloc change sur le corpus (faux positif supprimé) ; 0 nouvel écart ailleurs ; une unité réellement perdue reste signalée (test) |
| F29 D | DOC-006 p004-b0015 : `CRITICAL_ENTITY_MODIFIED` + `HALLUCINATION_ENTITY_MODIFIED` | un mois et une année **collés** par l’OCR n’étaient pas reconnus comme date mais comme « code » immuable | date mois-année tolérant l’absence d’espace | 1 alerte en moins sur DOC-006 ; une date réellement modifiée reste signalée (test) |

Tests : `backend/tests/unit/test_run27_regressions.py` (A ×5, B ×3, C ×3, D ×2).

## 2. Mémoire de traduction rejouée sans la garde courante — lacune d’outil

- Constat : le lanceur réutilisait une cible **et** ses alertes depuis la mémoire sans appliquer la garde d’entités courante. Les correctifs F29 n’auraient donc jamais été exercés en rejeu : le chiffre inventé de DOC-005 serait resté accepté et les ordinaux de DOC-006 seraient restés refusés.
- Correctif (`tools/interim_owner_corpus_run.py`) : une réutilisation est **invalidée** si le bloc avait été rejeté par la garde ou si la garde courante la refuse ; le bloc est renvoyé au service réel. La télémétrie expose `translation_memory.invalidated_by_current_guard`.
- Mesure hors ligne sur la mémoire run26b : exactement 4 blocs invalidés (les 4 blocs P0). Tests E ×3.

## 3. Ordinal français invalide — F34 (introduit puis corrigé pendant RUN27)

- Run intermédiaire run27 : la protection F29 A rend le nombre d’un ordinal anglais au modèle, qui ne traduit que le suffixe ; la cible française obtenue est **un ordinal invalide** (suffixe « er » après un nombre différent de 1). Vérifié dans la cible privée.
- Cause : aucune garde de plausibilité de la cible française pour les ordinaux.
- Correctif : `_restore_and_validate(target_language)` refuse une cible française où « er / re / ère » suit un nombre différent de 1 (`IMPLAUSIBLE_TARGET_ORDINAL`, erreur, source conservée → `FAILED implausible_target`) ; la mémoire invalide ces réutilisations.
- Mesure hors ligne sur toutes les cibles run27 : 1 seul refus (le bloc fautif), 0 autre. Run verdict run27b : le modèle redonne la même cible invalide, elle est refusée, l’original est conservé. Le bloc n’est **pas** traduit : défaut ouvert, mais plus d’erreur imprimée.
- Tests F34 ×3 ; mutation M8 (règle neutralisée) : 2 échecs.

## 4. Rendu (P0) — F30, F31, F32, F33

| Réf. | Reproduction | Cause racine | Correctif | Effet mesuré (rejeu de rendu des 8 documents, même entrée) |
| --- | --- | --- | --- | --- |
| F30 | **Régression F25 de RUN26** (DOC-007 p001-b0041 : valeur non rendue quand son libellé passe en revue), reproduite au pixel hors ligne (426/2 816 px d’encre découverte, 0,1513) | `_shrink_away` testait d’abord le côté horizontal : un voisin conservé juste au-dessus, mais dont le centre est à gauche, coupait toute la partie gauche du masque → encre propre découverte → rendu refusé | réduction du côté qui retire la **moindre surface** (égalité → horizontal) | `SCAN_TEXT_OVER_SOURCE_INK` 10 → 4 ; +6 blocs placés, 0 perdu ; pages modifiées seulement DOC-004 2/2, DOC-005 1/2, DOC-007 2/5 |
| F31 | Effet de bord F30 trouvé à la revue des planches : DOC-007 p003-b0043 placé mais **hauts de lettres source visibles** (masque réduit sur toute la largeur pour un voisin étroit) — invisible au contrôle d’encre, qui ne mesure que sous les lignes dessinées | le masque réduit ne couvrait pas les parties du masque plein éloignées du voisin conservé | compléter le masque réduit par les **pièces** du masque plein qui ne touchent aucun voisin conservé ; **garde de propriété** (les composantes d’encre touchées doivent être à ≥ 90 % dans la zone déjà masquée) ; **garde couleur** (encre colorée dans le masque plein de la ligne → aucune pièce : tampons, signatures, annotations) | première version sans garde : **régression** détectée sur planche (tampon bancaire effacé, DOC-006 p. 2) → gardes ajoutées ; version finale : `SCAN_TEXT_OVER_SOURCE_INK` 10 → 2, +8 blocs placés, 0 perdu, tampons intacts, 13 zones modifiées toutes revues |
| F32 | DOC-006 : 12 pages en `RENDER_TEXT_MASK_TOO_LARGE` + `VISUAL_MASK_TOO_LARGE` (couverture 0,365–0,742) | `render_metrics` et le scorer visuel **additionnaient** les aires des masques de lignes et de blocs, qui se recouvrent (somme ≈ 1,65 × l’union) ; l’union réelle est ≤ 0,281 par page | aire de l’**union** exacte (`backend/app/documents/geometry.py`), seuil 0,35 inchangé | 30 alertes en moins (DOC-004 2, DOC-006 24, DOC-007 4) : **erreurs de mesure**, les masques n’ont pas changé ; ce n’est pas une amélioration du rendu |
| F33 | DOC-005 : ligne de pied de page déjà en français, « traduite » FR→FR et re-typographiée (ponctuation doublée réduite) puis comptée comme traduite | la clé typographique ne réduisait pas une ponctuation répétée identique | une ponctuation répétée identique est de la typographie (jamais les mots ni les chiffres) | exactement 2 blocs du corpus reclassés `model_returned_source` (déjà en français, original conservé) |

Tests : `backend/tests/unit/test_run27_render_regressions.py` (F30 ×2, F31 ×7 dont une contre-épreuve, F32 ×3, F33 ×3). Mutations M1–M7 : 7/7 détectées.

## 5. Dérive de la règle de mesure

Voir RUN27-SCORE-AUDIT.md § 4 : la mesure importe des règles produit ; F33 a reclassé deux blocs **historiques** de DOC-005. Correctif : double mesure à règle identique et empreinte de règle `tools/recette/ruler_fingerprint.py` (3 tests).

## 6. Défauts révélés par le contrôle visuel des PDF (non vus par les métriques)

| Id | Document | Constat | Statut |
| --- | --- | --- | --- |
| MV-02 | DOC-007 | run26b : deux cases cochées rendues comme cases vides (l’état coché, lu par l’OCR comme des caractères parasites, disparaissait à la traduction) — défaut critique invisible aux métriques | **corrigé** par F29 B : blocs en revue humaine, original conservé (cases cochées visibles) |
| MV-01 | DOC-005 | **régression RUN27** : un identifiant dont l’OCR a lu un chiffre comme une lettre. En run26b la cible était juste par hasard ; en run27b, le bloc (ligne française détectée comme une autre langue) est traité FR→FR, la garde compare à l’OCR erronée et accepte → identifiant **faux** dans le PDF | **ouvert, critique** ; non corrigé : lisser la langue d’un bloc d’après ses voisins risquerait des omissions silencieuses ; la vraie correction est une référence humaine ou une relecture OCR ciblée des identifiants |
| MV-03 | DOC-007 | ligne justifiée mi-source mi-français (mots en blocs séparés) | ouvert, préexistant (segmentation) |

## 7. Causes non corrigées (voir RUN27-OPEN-ISSUES.md)

- DOC-004 : 16 débordements en run27b (`LAYOUT_OVERFLOW`, blocs `FAILED render_overflow`, original conservé). Sur les 17 de run26b : 9 lignes arabe → français trop longues à la police minimale, 8 boîtes OCR plus basses que l’interligne minimal ; un bloc est passé en revue humaine (F29 B), sans correction du débordement lui-même. Correction envisagée : croissance verticale contrôlée dans un blanc vérifié — non faite, risque de collision.
- `PROTECTED_REGION_CHANGED` (DOC-004, 6), `UNMAPPED_TABLE_CONTENT` (DOC-007, 1), `RENDER_*_MISSING` résiduels (6 documents, 1 chacun) : non corrigés.
- DOC-006 p004-b0015 : bloc d’élément visuel protégé envoyé quand même au modèle (cible stockée, non rendue) : incohérence de pipeline sans effet sur le PDF.
