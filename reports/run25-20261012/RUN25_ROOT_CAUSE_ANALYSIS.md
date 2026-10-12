# RUN25 — Analyse des causes racines

Ce document recense chaque défaut traité pendant la recette run25, avec pour chacun le symptôme initial, la cause
technique établie, le fichier et la fonction concernés, la correction, le test et le résultat avant/après (prompt
run25 §2 et §18). Les défauts analysés mais non corrigés figurent en §4, avec leur cause quand elle est établie.

Aucun texte de document, nom de fichier, empreinte de document ni chemin privé ne figure ici. Les documents sont
désignés par DOC-001 à DOC-008. Les blocs sont désignés par leur identifiant de position (`pPPP-bBBBB` : page et
rang du bloc dans l'IR), qui ne contient aucun contenu.

## 1. Point de départ et méthode

| Élément | Constat |
|---|---|
| Code de départ | commit `026b0f9` (verdict run18 = run24, empreinte du code exécuté `4d4956273c97d866`) ; l'archive de code fournie est identique à l'arbre Git de ce commit (comparaison récursive vide) |
| Preuves fournies | manifeste SHA-256 vérifié (297 fichiers) ; chiffres de tests cités au §1 du prompt retrouvés dans les journaux : 591 tests backend, golden 8/8, 16 tests Angular, build, Ruff, pip-audit, npm audit |
| Cohérence des runs | le « verdict run18 » des rapports précédents correspond au répertoire run24 ; ses résumés par document ne portaient pas de version de code. Les scripts privés de run25 écrivent l'empreinte du code exécuté et le HEAD dans `FINGERPRINT.txt` de chaque run ; le lanceur versionné n'est pas modifié |
| Baseline immuable | baseline du 08/10, run17 et run24 figés avant toute modification (liens physiques en lecture seule, manifeste SHA-256 privé de 1 520 fichiers) |
| Outil de relecture | relecture instrumentée privée du rendu : réutilisation de l'analyse et des traductions de run24, **zéro requête au moteur IA**, journal de chaque décision du moteur de rendu (cadres candidats, voisins, origine des pixels d'encre résiduelle) sans texte |
| Registre d'anomalies | nouvel outil versionné `tools/recette/anomaly_register.py` : une ligne par bloc défectueux, mêmes règles pour tous les runs que `measure_v2` (périmètre attendu indépendant du run, statuts §11, rendu mesuré dans le PDF produit) |
| Mesure | méthode unique `measure-v2.1-run18` appliquée à baseline, run17, run24, run25 intermédiaire et run25 final |

Les traductions de tous les runs run25 proviennent de la **mémoire de traduction de run24** (signature de contenu
identique) : aucune nouvelle traduction n'a été générée pour le verdict. Les écarts run24 → run25 sont donc
attribuables au seul code, sans variance du moteur IA. Un run supplémentaire à génération Interim réelle est traité
à part (voir `RUN25_TRANSLATION_COVERAGE_REPORT.md`).

## 2. Chaîne des runs run25

| Run | Code (empreinte) | Contenu | Rôle |
|---|---|---|---|
| tentative 1 | `0c1d77bf17abe555` | arrêt avant traduction ×8 : droits d'écriture sur les copies de la baseline en lecture seule | échec du script, conservé ; corrigé (droits sur les copies uniquement) |
| run25 (« run25a ») | `0c1d77bf17abe555` | F20, F20b, F21 | intermédiaire : régression visuelle détectée (filet de cadre effacé, D3) |
| run25b | `12cd5235d720627c` | + F22 | intermédiaire : F22 incomplet (filet toujours effacé, mesure numérique) |
| run25c | `889fd05e1dd1fbfb` | + F22b | intermédiaire |
| run25d | `e1e041cfccaae48e` | + F23 | intermédiaire |
| **run25e** | **`f4a84aaef38c7c7d`** | + F24 | **verdict run25** |

Chaque run : 8 documents terminés, 0 requête Interim, 0 violation de budget, empreintes SHA-256 des 8 originaux
inchangées, statut `REVIEW_REQUIRED` pour les 8 documents.

## 3. Défauts corrigés

### Synthèse

| Id | Documents | Défaut | Fichier / fonction | Tests | Effet mesuré (run24 → run25 final) |
|---|---|---|---|---|---|
| F20 | DOC-004, DOC-006, DOC-007 | traductions refusées pour « encre résiduelle » à cause de boîtes OCR gonflées | `pdf_fidelity.py` `_vertical_ink_split`, `_scan_covers` | 4 | `SCAN_TEXT_OVER_SOURCE_INK` 19 → 9 (avec F20b) |
| F20b | DOC-004, DOC-007 | cadre d'une ligne ancré sur le haut d'une boîte gonflée | `pdf_fidelity.py` `_glyph_band`, `_plan_scan_block` | 2 | 13 blocs récupérés, 0 dégradé (relecture) |
| F21 | DOC-007 | cases à cocher vides effacées sous une traduction | `line_verification.py` `flag_misread_checkbox_tokens` | 2 | 5 cases conservées ; bloc `UNCERTAIN` |
| F22 / F22b | DOC-007 (corpus : environ 43 masques) | filet de cadre effacé par le masque d'un titre | `pdf_fidelity.py` `_clip_cover_off_rules`, `_longest_run`, `_scan_covers`, `_plan_scan_block` | 5 | filet 0,03 → 1,00 (part sombre du rang) |
| F23 | DOC-004, DOC-008 | numéros multi-groupes inversés en contexte RTL (donnée critique) | `line_verification.py` `flag_bidi_number_runs` | 2 | 2 lignes fausses retirées du rendu ; originaux conservés |
| F24 | DOC-004, DOC-005, DOC-006, DOC-007, DOC-008 | encre originale effacée par la marge des masques | `pdf_fidelity.py` `_pull_padding_off_foreign_ink`, `_scan_covers` | 4 | encre effacée hors blocs écrits 13 117 → 6 573 px (−50 %) |

### F20 — Refus « encre résiduelle » provoqués par des boîtes OCR gonflées

* **Symptôme initial.** En run24, 19 blocs traduits n'étaient pas écrits (`SCAN_TEXT_OVER_SOURCE_INK` :
  DOC-004 ×8, DOC-007 ×8, DOC-006 ×2, DOC-005 ×1). La source restait visible alors qu'une traduction existait.
  Ces refus touchaient surtout des lignes de cellules et de clauses en DOC-004 et DOC-007.
* **Cause identifiée** (19 refus sur 19, établie par relecture instrumentée). La boîte OCR de la ligne est 2,5 à
  3 fois plus haute que l'impression et chevauche la ligne voisine. Le masque est alors réduit au bord de la boîte
  voisine (`_shrink_away`), ce qui laisse les jambages de la ligne hors du masque. Le contrôle d'encre
  (`_drop_text_over_source_ink`) retire alors la traduction, et le refus se propage en cascade quand le voisin est
  conservé.
* **Fichier et fonction.** `backend/app/documents/pdf_fidelity.py` : nouvelle fonction `_vertical_ink_split`,
  appelée dans `_scan_covers` quand la page est disponible.
* **Correction appliquée.** Le chevauchement vertical entre deux lignes OCR est partagé au creux du profil d'encre :
  composantes connexes ; une marque flottante est attribuée à la ligne la plus proche ; le partage est refusé si un
  trait relie les deux lignes ou si l'attribution est ambiguë. Dans ces deux cas, l'ancien comportement s'applique.
  Le contrôle final de `_scan_covers` porte sur la liste des voisins départagés.
* **Tests.** `test_f20_split_lies_in_the_ink_valley_between_two_lines`,
  `test_f20_split_refused_when_a_stroke_joins_both_lines`,
  `test_f20_cover_reaches_own_descenders_without_touching_neighbour_print`,
  `test_f20_without_page_keeps_previous_behaviour`.
* **Avant/après.** Seul, F20 récupère 1 refus sur 19 : le cadre de rendu restait mal placé (voir F20b). Avec F20b :
  13 blocs récupérés et 0 dégradé en relecture à traductions identiques (DOC-004 +5, DOC-006 +1, DOC-007 +7). Les
  caractères manquants, coupés ou sur encre passent de 3 102 à 2 623. Run final : `SCAN_TEXT_OVER_SOURCE_INK`
  passe de 19 à 9.

### F20b — Cadre d'une ligne ancré sur le haut d'une boîte gonflée

* **Symptôme initial.** Même symptôme que F20 : le texte français était dessiné dans la bande d'interligne ou sur
  l'encre de la ligne voisine, puis retiré par le contrôle d'encre.
* **Cause identifiée.** Le cadre d'une ligne unique est borné en hauteur (au plus 1,45 fois la taille de police) et
  ancré en haut de la boîte OCR. Quand la boîte est gonflée, ce haut ne correspond plus à l'impression.
* **Fichier et fonction.** `pdf_fidelity.py` : nouvelle fonction `_glyph_band`, utilisée dans `_plan_scan_block`.
* **Correction appliquée.** Quand la boîte dépasse 1,15 fois la hauteur d'une ligne, le cadre d'une ligne est
  centré sur la bande d'impression propre de la ligne. L'encre contenue dans les boîtes OCR des autres lignes est
  masquée avant le calcul. Le plafond `min(bas de boîte, haut + une ligne)` est conservé.
  La première version, qui se fondait sur un bord partagé, a été rejetée : elle provoquait une régression en
  DOC-007 `p001-b0010`, parce qu'un fragment OCR voisin était contenu dans la boîte. La version retenue masque les
  boîtes voisines et ne provoque aucune régression.
* **Tests.** `test_f20b_glyph_band_ignores_ink_boxed_by_another_line`, `test_f20b_glyph_band_none_on_blank_box`.
* **Avant/après.** Voir F20 (effet combiné). Les recadrages privés de DOC-004 p1 et DOC-007 p1 (original, run24,
  relecture) ont été ouverts : les lignes récupérées sont lisibles, sans chevauchement de l'original.

### F21 — Cases à cocher vides effacées sous une traduction (DOC-007 p1)

* **Symptôme initial.** Après F20, la relecture rend traduite la ligne d'options `p001-b0091` de DOC-007, qui
  comporte 5 cases vides. Les cases disparaissent sous le masque, et le moteur IA a supprimé les jetons OCR qui les
  représentaient. En run24, la ligne n'était protégée que par hasard, par un refus en cascade : il s'agit d'une
  régression latente que F20 a révélée.
* **Cause identifiée.** Ces cases ouvertes ou fines échappent au détecteur de cases (`checkbox_glyphs`) : aucune
  région protégée n'est créée, et l'OCR les lit comme des jetons parasites (`LJ`, `L]`, `|_|`, `[_]`).
* **Fichier et fonction.** `backend/app/documents/line_verification.py` : nouvelle fonction
  `flag_misread_checkbox_tokens`, appelée dans `verify_lines` ; version `line-verification-8`.
* **Correction appliquée.** Une ligne sans case détectée qui porte de tels jetons (motif strict, sensible à la
  casse, au moins un jeton isolé) devient `ocr_unreliable` (`checkbox_misread_undetected`). Le bloc passe en
  `UNCERTAIN`, n'est pas envoyé au moteur IA, et la source est conservée avec ses cases. Une case cochée saisie
  sous la forme `[X]` n'est pas concernée.
* **Tests.** `test_f21_misread_checkbox_tokens_make_the_line_unreliable`,
  `test_f21_detected_box_or_ordinary_text_is_not_flagged`.
* **Avant/après.** La calibration sur tout le corpus trouve 1 bloc et 4 jetons, sans autre bloc touché. En run25,
  le bloc est `UNCERTAIN` et les cases sont intactes (recadrage privé ouvert). En contrepartie, DOC-007 compte
  114 caractères tentés de moins (8 044 → 7 930).
* **Limite de preuve.** La relecture (`--reuse-translations`) contourne le filtre `ocr_unreliable` du service de
  traduction. F21 n'est donc prouvé que par le vrai run (`--translation-cache`), où le bloc n'est pas envoyé.

### F22 et F22b — Filet de cadre effacé par le masque d'un titre (DOC-007 p1)

* **Symptôme initial.** En run25a, une nouvelle région altérée apparaît sur la bande de formulaire de DOC-007 p1 :
  le filet supérieur du cadre est effacé sur la largeur du titre `p001-b0038`. La part sombre maximale du rang du
  filet vaut 1,00 sur l'original et en run24, mais 0,03 en run25a. Le défaut a été introduit par F20b, qui avait
  rendu ce titre écrivable.
* **Cause identifiée.** La boîte OCR du titre touche le filet (boîte gonflée par le filet), et le masque, soit la
  boîte plus sa marge, recouvre le filet.
  Une première correction (F22) était **incomplète** : le masque complet calculé par `_plan_scan_block` (utilisé
  quand tous les voisins chevauchés sont remplacés) appelait `_scan_covers` sans la page, si bien que F22 n'y était
  pas appliqué. La lecture visuelle initiale qui concluait à une bordure restaurée était **fausse**. La mesure
  numérique du filet l'a démentie (run25b : 0,03), d'où F22b.
* **Fichier et fonction.** `pdf_fidelity.py` : nouvelles fonctions `_clip_cover_off_rules` et `_longest_run`,
  appelées en fin de `_scan_covers` ; F22b ajoute `page=page` à l'appel du masque complet dans `_plan_scan_block`.
* **Correction appliquée.** Un filet est une suite continue d'encre couvrant au moins 85 % de la largeur du masque
  (90 % de la hauteur pour un filet vertical), située dans une bande de bord et dépassant le masque d'au moins 2 px.
  Le masque est rogné avant ce filet. La première version, fondée sur une part d'encre d'au moins 0,7, a été
  rejetée : des lignes de texte denses étaient prises pour des filets, ce qui créait 7 refus nouveaux.
* **Tests.** `test_f22_cover_pulled_back_from_frame_rules_but_keeps_the_print`,
  `test_f22_dense_text_rows_are_not_mistaken_for_rules`,
  `test_f22_line_not_continuing_past_the_cover_is_not_a_rule`, `test_f22_without_page_keeps_previous_behaviour`,
  `test_f22b_plan_full_cover_stays_off_frame_rules`. Contre-épreuve : ce dernier test échoue sans F22b.
* **Avant/après.** Part sombre du filet : 1,00 sur l'original, 1,00 en run24, 0,03 en run25a et run25b, 1,00 en
  run25c et après. Environ 43 masques sont rognés dans le corpus. Le registre d'anomalies ne compte aucun refus
  ajouté ni perdu. Le zoom privé de la bande (original, run24, run25b, run25 final) a été ouvert après la mesure.

### F23 — Numéros multi-groupes inversés en contexte RTL (DOC-004 p1, DOC-008 p1)

* **Symptôme initial.** Sur la planche finale de DOC-008 p1, la ligne de coordonnées du pied de page est rendue en
  français avec les groupes de chiffres des numéros inversés. En DOC-004 p1 `p001-b0105`, un numéro est rendu avec
  ses groupes inversés, un second est tronqué et la fin du numéro original est effacée par le masque. Il s'agit
  d'une **donnée critique altérée**, présente dès run24 : ce n'est pas une régression run25.
* **Cause identifiée.** En contexte RTL, Tesseract émet un nombre LTR multi-groupes dans l'ordre inverse des groupes.
  La source OCR est donc déjà fausse, et le garde-fou d'entités, qui compare la source à la cible, ne peut pas le
  voir.
* **Fichier et fonction.** `line_verification.py` : nouvelle fonction `flag_bidi_number_runs`, appelée dans
  `verify_lines` ; version `line-verification-9`.
* **Correction appliquée.** Une ligne OCR en contexte RTL (lettres arabes ou hébraïques, ou marques bidi) qui porte
  au moins deux groupes numériques consécutifs, chaque groupe se terminant par un chiffre, devient `ocr_unreliable`
  (`bidi_number_order_unreliable`). Le bloc passe en `UNCERTAIN`, n'est pas envoyé au moteur IA, et ses pixels
  originaux sont conservés.
* **Tests.** `test_f23_rtl_line_with_multi_group_number_is_kept_as_image`,
  `test_f23_single_numbers_or_ltr_context_are_not_flagged`. Contre-épreuve : le cas positif échoue sans F23.
* **Avant/après.** La calibration retient 3 lignes : `DOC-004 p001-b0100` (déjà `UNCERTAIN`), `p001-b0105` et
  `DOC-008 p001-b0045`. Un faux positif (une énumération) a été éliminé en exigeant qu'un groupe se termine par un
  chiffre, et 29 lignes multi-groupes en contexte LTR restent intactes. Le recadrage privé des deux lignes a été
  ouvert : numéros et pictogrammes originaux intacts.
  Contrôle indépendant des séquences de chiffres source/cible sur les 159 blocs traduits qui en contiennent :
  1 seul écart, qui est une correction OCR légitime vérifiée sur l'original ; aucune altération.
  **Coût assumé :** la couverture écrite de DOC-008 baisse de 0,640 à 0,591 (−85 caractères) et DOC-004 perd
  35 caractères tentés. Ces caractères étaient « écrits » mais faux.

### F24 — Encre originale effacée par la marge des masques

* **Symptôme initial.**
  * DOC-005 p2 : le premier glyphe d'une ligne française conservée est effacé par le masque de la ligne traduite
    voisine.
  * DOC-004 p1 : des bordures de rangées de tableau sont amincies ou interrompues.
  * DOC-006 : des soulignements de titres et des filets de formulaire sont touchés.

  La mesure de l'encre perdue *dans* les boîtes conservées ne voyait pas ce défaut, puisque cette encre se trouve
  hors de toute boîte OCR. Le défaut est préexistant (présent en run24).
* **Cause identifiée.** La marge fixe du masque (1,5 pt en vertical, 3 pt en horizontal) s'étend hors de la boîte
  OCR sans que le contenu recouvert soit examiné. F22 n'agit que sur un filet couvrant au moins 85 % de la largeur
  et dépassant le masque.
* **Fichier et fonction.** `pdf_fidelity.py` : nouvelle fonction `_pull_padding_off_foreign_ink`, appelée dans
  `_scan_covers` avant F22.
* **Correction appliquée.** La correction n'agit que dans les bandes de marge :
  * en haut et en bas, une rangée qui contient un trait continu d'au moins
    `max(4, min(max(0,3·largeur, 2,5·hauteur), 0,9·largeur))` px arrête le masque avant elle ;
  * sur les côtés, une encre étrangère située après une colonne vierge, ou après une marge intérieure vierge de 2 px
    entièrement dans la boîte (arrondi plancher/plafond), arrête le masque avant elle.

  Les accents et le débord propre contigu restent couverts.
* **Tests.** `test_f24_underline_or_row_rule_in_the_padding_is_not_covered`,
  `test_f24_neighbour_glyph_after_a_blank_gap_is_not_covered`,
  `test_f24_separator_printed_on_the_box_edge_after_a_blank_margin`,
  `test_f24_accents_and_own_overhang_are_still_covered`. Contre-épreuve sans F24 : 3 échecs, et 1 succès pour le
  cas négatif.
* **Avant/après.** Encre originale effacée hors des boîtes des blocs écrits (outil privé de mesure du débord de
  masque) : 141 grappes / 13 117 px en run24, 129 grappes / 6 573 px en run25 final (−50 %).

  | Document | run24 (px) | run25 final (px) | Écart |
  |---|---|---|---|
  | DOC-004 | 4 383 | 1 743 | −2 640 |
  | DOC-006 | 5 460 | 3 330 | −2 130 |
  | DOC-008 | 2 231 | 809 | −1 422 |
  | DOC-007 | 791 | 517 | −274 |
  | DOC-005 | 165 | 87 | −78 |

  En DOC-008, le nombre de grappes passe de 11 à 14 par fragmentation : chaque grappe run25 chevauche une grappe
  run24 et aucune n'est nouvelle. Le glyphe de DOC-005 est restauré (zoom privé ouvert). Le registre d'anomalies
  est strictement identique avant et après F24. En relecture, une grappe nouvelle de 95 px est apparue : un filet
  de 0,3 pt aminci mais encore visible (DOC-004 `p001-b0106`).

## 4. Défauts analysés et non corrigés

| Document | Défaut | Volume (run25 final) | Cause établie | Pourquoi non corrigé |
|---|---|---|---|---|
| DOC-004 | débordements `LAYOUT_OVERFLOW` | 14 blocs, 517 car. | 9 lignes arabes en cellule dont la cible française est 1,2 à 2 fois plus longue ; 1 boîte/police ; 4 micro-cellules dont la cause n'est pas établie | la police est déjà au plancher (72 %) ; baisser ce plancher ou déborder de la cellule est interdit (§4, §16) ; le refus conserve la source, sans perte |
| DOC-007 | débordements | 8 blocs, 354 car. | 7 lignes uniques p1 où **la source elle-même** ne tient pas dans sa boîte à la taille choisie : la police de rendu est plus large que la police scannée condensée ; 1 traduction 1,45 fois plus longue (p3) | correction juste = police condensée ou mise en page alternative, non disponible ; le seuil n'est pas modifié |
| DOC-001, DOC-006, DOC-008 | débordements | 2, 3 et 2 blocs | boîtes très petites ou OCR de faible confiance, traduction plus longue, voisin original à droite | même raison |
| DOC-002, DOC-004, DOC-005, DOC-006, DOC-007 | refus « encre résiduelle » restants | 9 blocs | encre d'une région protégée ou d'un voisin non séparable au creux (le partage F20 refuse, par construction) | le refus est la décision sûre |
| DOC-004, DOC-007, DOC-008 | `FAILED:model_returned_source` | 264, 537 et 388 car. | en DOC-008, uniquement des noms, adresses, sociétés et domaines (conservation correcte mais classée `FAILED`) ; en DOC-007 et DOC-004, OCR illisible et noms propres | le reclassement en `PRESERVED_INTENTIONALLY` exige un détecteur de noms propres plus large, au risque de masquer de vrais échecs : non fait, ces blocs restent comptés en revue humaine |
| DOC-004, DOC-007 | OCR de faible confiance traduit et écrit | 20 et 23 blocs | une ligne OCR illisible est traduite comme un texte valide (mot inventé, nombre) | visible dans le registre (`LOW_OCR_CONFIDENCE_TRANSLATED`) ; le filtre de confiance n'a pas été durci, pour ne pas changer les seuils |
| DOC-004 | traduit et placé mais introuvable dans le PDF | 45 car. absents, 99 partiels | non établie : mesure ou rendu | à instruire |
| DOC-007 | `UNMAPPED_TABLE_CONTENT` | 1 | tableau candidat sans bloc membre (réel, déjà constaté en run18) | alerte légitime conservée |
| DOC-006 | alertes d'entités critiques | 97 lignes au registre | formats de dates/unités et entités modifiées par le moteur | blocage de validation automatique conservé ; revue humaine |
| DOC-007 | titre `p001-b0038` | 1 | rendu en taille du corps, en gras, plus large que l'original condensé (confiance OCR inférieure au seuil de taille propre) | esthétique, sans perte ; seuil inchangé |

Ces limites sont reprises et chiffrées dans `LIMITATIONS.md`.

## 5. Erreurs de méthode reconnues pendant run25

* **Lecture visuelle erronée.** La bordure de DOC-007 a d'abord été jugée restaurée sur un zoom. La mesure
  numérique l'a démenti, d'où F22b. Depuis, chaque conclusion visuelle sur un filet est appuyée par une mesure.
* **Tentative 1 de run25.** L'échec par droits d'écriture sur les copies d'une baseline en lecture seule a été
  conservé et corrigé dans le script privé.
* **Périmètre de tests.** Une relance de la suite limitée à unit et integration a été identifiée comme erreur de
  périmètre, renommée, puis relancée sur le périmètre exact de la CI.
* **Relecture et filtre `ocr_unreliable`.** La relecture à traductions rejouées contourne ce filtre : les
  conclusions F21 et F23 reposent donc sur les vrais runs.
