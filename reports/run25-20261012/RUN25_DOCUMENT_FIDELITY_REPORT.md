# RUN25 — Rapport de fidélité documentaire

Ce rapport porte sur la fidélité du PDF produit par le run final (run25e, code `f4a84aaef38c7c7d`) à l'original :
pagination, tableaux et cellules, cases à cocher, bordures, cachets, signatures, logos, données critiques, mise en
page et zones à revoir. Il couvre les prompts run25 §3 à §13 et §16.

Les documents sont désignés par DOC-001 à DOC-008, les blocs par leur identifiant de position (`pPPP-bBBBB`). Les
coordonnées sont en points PDF (origine en haut à gauche). Aucun texte de document, nom de fichier ni empreinte de
document ne figure ici.

## 1. Sources de preuve

| Preuve | Nature | Portée |
|---|---|---|
| Contrôles du moteur (`issues`, `block_status`, scores) | produits par l'application à chaque run | bloquants : alertes critiques ⇒ `REVIEW_REQUIRED` |
| Mesure de rendu v2.1 (`render_outcome.py`) | extraction indépendante du texte du PDF produit | blocs écrits, partiels ou absents, collisions, hors page |
| Audit des régions graphiques (`compare_runs_sheets.py`) | part de pixels modifiés par région candidate, comparée à l'original | une région est « altérée » au-delà de 2 % |
| Débord de masque (outil privé) | pixels sombres de l'original devenus clairs **hors** des boîtes des blocs traduits écrits | filets, soulignements, glyphes voisins effacés |
| Mesure de filet (outil privé) | part sombre maximale d'un rang de pixels | continuité d'une bordure précise |
| Registre d'anomalies (`anomaly_register.py`) | une ligne par bloc défectueux, avec page, coordonnées et codes | localisation des zones à revoir |
| Inspection visuelle | recadrages et planches **réellement ouverts**, listés au §2 | constats qualitatifs |

## 2. Inspections visuelles réellement effectuées en run25

Conformément au §2 du prompt, seuls les rendus réellement ouverts sont cités.

| Document | Vues ouvertes (privées) | Constat |
|---|---|---|
| DOC-004 | planche p1 (original, baseline, run17, run24, run25) ; recadrages des blocs récupérés (F20/F20b) ; ligne du numéro `p001-b0105` ; lignes téléphone (F23) ; grappes de débord (bordures `p001-b0043`, `p001-b0102`, `p001-b0002`) avant/après F24 ; nouvelle grappe `p001-b0106` | lignes récupérées lisibles et sans chevauchement ; numéros originaux conservés après F23 ; bordures restaurées par F24 ; filet de 0,3 pt aminci mais visible en `p001-b0106` |
| DOC-005 | recadrages `p002-b0033` et jonction `b0033`/`b0034` ; zoom du premier glyphe avant/après F24 | glyphe effacé en run24, restauré en run25 |
| DOC-006 | audit des régions graphiques (run25) ; grappes de débord (soulignement de titre, filets de formulaire) avant/après F24 | régions « cachet/logo » altérées = lignes de titre ou texte surligné traduits, surlignage conservé ; signature p3 intacte ; soulignement conservé après F24 |
| DOC-007 | recadrage des cellules refusées p1 ; blocs récupérés p1 bas ; ligne d'options `p001-b0091` (cases) ; région nouvellement altérée p1 ; bande de formulaire p1 (original, run24, run25b, run25 final) | cases conservées (F21) ; filet de cadre restauré, confirmé par mesure (§5) ; titre `p001-b0038` plus large que l'original condensé |
| DOC-008 | planche p1 (original, baseline, run17, run25) ; pied de page p1 (original, run24, run25, différence) ; ligne de coordonnées (F23) | numéros inversés en run24 ; ligne conservée en original en run25 ; cachet, signature et certification intacts |
| DOC-001 | audit des régions graphiques (run25) | 3 logos à 0 % ; 5 régions « cachet/logo » altérées = lignes de titre surlignées traduites |

**Non ouverts en run25** : les planches complètes de DOC-002, DOC-003, DOC-005, des pages de DOC-006, des pages 2 à 5
de DOC-007 et de la page 2 de DOC-008. Pour ces vues, le constat repose sur les mesures numériques (identiques à
run24 sauf mention) et sur l'audit visuel de run18, qui portait sur le même code de rendu pour ces zones.

## 3. Pagination et structure

| Document | Pages source → produit | Tableaux candidats | Cellules tracées | Statut du rendu des cellules (run25 = run24) |
|---|---|---|---|---|
| DOC-001 | 2 → 2 | 2 | 283 | 279 inchangées, 4 rendues par bloc (cellule de scan ambiguë) |
| DOC-002 | 1 → 1 | 1 | 1 | 1 rendue par bloc (protégée) |
| DOC-003 | 1 → 1 | 0 | 0 | — |
| DOC-004 | 2 → 2 | 2 | 10 | 4 inchangées, 4 cellules ambiguës, 2 protégées |
| DOC-005 | 2 → 2 | 2 | 2 | 2 protégées |
| DOC-006 | 16 → 16 | 10 | 25 | 12 inchangées, 6 ambiguës, 7 rendues dans un cadre de scan |
| DOC-007 | 5 → 5 | 5 | 168 | 159 inchangées, 9 ambiguës |
| DOC-008 | 2 → 2 | 2 | 797 | 793 inchangées, 4 ambiguës |

* **Pagination conservée : 8 documents sur 8** (`pages_preserved = true`).
* **Fidélité des tableaux : NON MESURÉE par le moteur.** Le contrôle de structure des tableaux renvoie
  `measured = false`, motif `no_real_table_detected`, sur les 8 scans. Les scores `STRUCTURE`, `TABLE`, `ENTITY` et
  `GLOBAL` valent `NULL` pour les 8 documents. Ils ne sont ni remplacés par une valeur par défaut, ni comptés comme
  réussis.
* Sur un scan, le moteur ne reconstruit pas le tableau. Il écrit chaque traduction dans le cadre de sa cellule au-dessus
  du raster, et le quadrillage reste l'image d'origine. Le risque porte donc sur l'effacement de bordures par les
  masques (traité au §5) et sur le placement d'une valeur hors de sa cellule. Aucun déplacement de valeur dans une autre
  cellule n'a été observé dans les vues ouvertes. Ce contrôle n'est toutefois pas exhaustif.
* Score `VISUAL` du moteur : 0,0 pour DOC-004, DOC-006 et DOC-007 (alerte critique `VISUAL_MASK_TOO_LARGE` ou région
  protégée modifiée) ; 0,87 à 0,94 pour les autres.

## 4. Régions graphiques

Les régions candidates sont détectées automatiquement sur l'original. Une région est comptée « altérée » quand plus
de 2 % de ses pixels diffèrent de l'original.

| Document | Régions (par type) | Altérées : baseline / run17 / run24 / run25 |
|---|---|---|
| DOC-001 | 10 cachet/logo | 0 / 5 / 5 / 5 |
| DOC-002 | 110 image, 4 monochromes, 109 vectorielles | 19 / 12 / 15 / 14 |
| DOC-003 | 110 image, 1 monochrome, 109 vectorielles | 0 / 2 / 2 / 2 |
| DOC-004 | **27 cases à cocher**, 3 monochromes, 216 vectorielles | 7 / 10 / 1 / 1 |
| DOC-005 | 220 image, 3 monochromes, 218 vectorielles | 4 / 3 / 5 / 5 |
| DOC-006 | 18 cachet/logo, 1 monochrome | 0 / 5 / 6 / 6 |
| DOC-007 | 7 monochromes, 541 vectorielles | 0 / 2 / 1 / 2 |
| DOC-008 | 221 image, **8 monochromes (cachet, signature, certification)**, 218 vectorielles | 33 / 50 / 48 / 46 |
| **Total** | 2 154 | 63 / 89 / 83 / 81 |

Constats run25 :

* **Les 81 régions altérées sont toutes chevauchées par un bloc traduit et écrit.** Elles sont localisées
  individuellement (document, page, coordonnées, type, part modifiée) dans l'export JSON (`altered_regions_run25`).
  Cette condition est nécessaire mais pas suffisante pour qu'il s'agisse d'un changement voulu.
* **Cachets, signatures, logos et éléments de certification : 0 % de modification.** Cela vaut pour les 3 logos de
  DOC-001, la signature de DOC-006 p3, les 8 régions monochromes de DOC-008 (dans tous les runs) et les 7 régions
  monochromes de DOC-007. Aucun cachet n'a été effacé pour faciliter le rendu (§11).
* Les régions « cachet/logo » altérées de DOC-001 (5) et DOC-006 (6), avec une part modifiée de 0,34 à 0,66 identique
  à run24, sont des lignes de titre ou de texte surligné traduites. Le surlignage reste visible derrière le français.
* **Cases à cocher de DOC-004 : 27 sur 27 à 0 %** en run24 et run25.
  * Cases altérées par run : 7 dans la baseline (part jusqu'à 74 %), 9 en run17 (jusqu'à 98 %), 0 en run24 et
    run25.
  * La seule région de DOC-004 altérée en run24 et run25 est monochrome, et non une case.
  * Les 8 alertes moteur `PROTECTED_REGION_CHANGED` sur ces cases sont maintenues (seuil plus strict).
* DOC-007 : la région de la bande de formulaire p1 passe de 0 à 0,044, du fait de la traduction des libellés. Le filet
  est restauré et les données sont intactes.
* DOC-008 : les 46 régions altérées sont des bandes d'image pleine largeur, d'environ 7,8 pt de haut, découpées par le
  détecteur, aux pages 1 et 2. Chacune est traversée par une ligne traduite et écrite. Leurs coordonnées figurent dans
  l'export.

## 5. Bordures, filets et encre effacée hors des blocs écrits

| Document | Grappes run24 | px run24 | Grappes run25 | px run25 | Écart |
|---|---|---|---|---|---|
| DOC-001 | 3 | 73 | 3 | 73 | 0 |
| DOC-002 | 1 | 14 | 1 | 14 | 0 |
| DOC-003 | 0 | 0 | 0 | 0 | 0 |
| DOC-004 | 51 | 4 383 | 41 | 1 743 | −2 640 |
| DOC-005 | 4 | 165 | 3 | 87 | −78 |
| DOC-006 | 58 | 5 460 | 54 | 3 330 | −2 130 |
| DOC-007 | 13 | 791 | 13 | 517 | −274 |
| DOC-008 | 11 | 2 231 | 14 | 809 | −1 422 |
| **Total** | 141 | 13 117 | 129 | **6 573** | **−50 %** |

* Mesure : pixels sombres de l'original (gris < 140, zoom 3) devenus clairs, hors des boîtes des blocs traduits
  écrits, regroupés en grappes 8-connexes d'au moins 12 px.
* Filet de cadre de DOC-007 p1 (sous le titre `p001-b0038`), part sombre maximale du rang : 1,00 sur l'original,
  1,00 en run24, 0,03 en run25a et run25b, **1,00 en run25 final**.
* **Il reste 6 573 px d'encre effacée**, dont un filet de 0,3 pt aminci mais encore visible en DOC-004 `p001-b0106`
  (95 px). Les bordures ne sont donc pas intégralement préservées, et ce point reste à revoir.

## 6. Mise en page du texte inséré

| Document | Blocs écrits / partiels / absents (run25) | Mots insérés | Collisions | Hors page | `LAYOUT_OVERFLOW` | Texte coupé (registre) |
|---|---|---|---|---|---|---|
| DOC-001 | 8 / 0 / 5 | 64 | 0 | 0 | 2 | 0 |
| DOC-002 | 8 / 0 / 1 | 56 | 0 | 0 | 0 | 0 |
| DOC-003 | 2 / 0 / 0 | 10 | 0 | 0 | 0 | 0 |
| DOC-004 | 81 / 1 / 25 | 461 | 0 | 0 | 14 | 1 |
| DOC-005 | 3 / 0 / 1 | 34 | 0 | 0 | 0 | 0 |
| DOC-006 | 264 / 2 / 11 | 4 692 | 0 | 0 | 3 | 2 |
| DOC-007 | 91 / 2 / 12 | 1 093 | 0 | 0 | 8 | 2 |
| DOC-008 | 22 / 0 / 3 | 169 | 0 | 0 | 2 | 0 |

* Aucune collision entre mots insérés en run24 et run25. Run17 en comptait 34 : 5 en DOC-004 et 29 en DOC-007.
* Un débordement n'est jamais forcé : le bloc est refusé et la source reste visible (`FAILED:render_overflow`). Le
  refus n'est pas compté comme une correction réussie, et le bloc reste au registre et en revue humaine.
* Causes des débordements restants (relecture instrumentée, détail dans `RUN25_ROOT_CAUSE_ANALYSIS.md` §4) :
  * DOC-007 : 7 sur 8 viennent d'une source qui ne tient pas elle-même dans sa boîte à la police de rendu (police
    scannée condensée) ; 1 vient d'une traduction plus longue ;
  * DOC-004 : 9 lignes arabes en cellule, dont la cible est 1,2 à 2 fois plus longue, avec une police déjà au
    plancher de 72 %.
* Taille de police : aucune réduction sous le plancher existant ; le seuil n'a pas été modifié (§4).
* Défaut esthétique non corrigé : le titre `p001-b0038` de DOC-007 est rendu à la taille du corps et en gras, plus
  large que l'original condensé.

## 7. Données critiques

* **F23** : deux lignes de coordonnées en contexte RTL (DOC-004 `p001-b0105`, DOC-008 `p001-b0045`) étaient rendues
  avec les groupes de chiffres de leurs numéros inversés. Elles ne sont plus traduites, et les pixels originaux sont
  conservés.
* **Contrôle indépendant des chiffres** : les séquences de chiffres de la source et de la cible ont été comparées pour
  les 159 blocs traduits et écrits qui en contiennent. Il n'y a qu'un écart : une correction OCR légitime, vérifiée sur
  l'original. Aucune altération n'a été trouvée.
* Alertes du moteur maintenues (run25) :

| Document | Alertes critiques d'entités | Lignes `CRITICAL_ENTITY_REVIEW` au registre |
|---|---|---|
| DOC-001 | — | 1 |
| DOC-002 | `PROTECTED_ENTITY_CHANGED` 1 | 1 |
| DOC-004 | — | 2 |
| DOC-005 | — | 2 |
| DOC-006 | `CRITICAL_ENTITY_MODIFIED` 2, `HALLUCINATION_ENTITY_MODIFIED` 1, `HALLUCINATION_UNIT_CHANGED` 1, `PROTECTED_ENTITY_CHANGED` 1 | 97 |
| DOC-007 | `PROTECTED_ENTITY_CHANGED` 1 | 39 |
| DOC-008 | — | 9 |

* Ces alertes bloquent toute validation automatique. Elles sont identiques à run24, sauf DOC-002 (voir
  `RUN25_REGRESSION_REPORT.md` §4).
* **Traduction d'un OCR de faible confiance.** Le registre compte des blocs traduits et écrits dont l'OCR est de
  faible confiance (`LOW_OCR_CONFIDENCE_TRANSLATED`) : 20 en DOC-004, 23 en DOC-007, 3 en DOC-006, 1 en DOC-002 et
  1 en DOC-008. Une ligne illisible peut ainsi être traduite comme un texte valide, et ces blocs exigent une relecture.

## 8. Zones non reconstruites et revue humaine

Le prompt (§3) demande que toute zone non reconstruite soit signalée et qu'un résultat exploitable soit fourni pour
la revue humaine, sans modifier l'original.

| Exigence | État |
|---|---|
| L'original n'est pas modifié | **oui** : empreintes SHA-256 des 8 originaux inchangées ; un bloc refusé garde ses pixels originaux |
| La zone est signalée | **oui** : statut par bloc (`FAILED`, `UNCERTAIN`) et motif ; `issues` portant `block_id` ; registre avec page, coordonnées et codes |
| Une altération visuelle est localisée par coordonnées (§5) | **oui** : régions altérées et lignes du registre, avec page et coordonnées dans l'export |
| La traduction proposée est conservée | **oui** : `translation.json` contient la cible même quand le rendu l'a refusée |
| L'écran de revue affiche, par zone, la page, le cadre et la traduction proposée | **partiel** : l'écran liste les problèmes par bloc (sévérité, message) et les blocs non traduits, avec les actions approuver, rejeter et corriger, et affiche les aperçus original, traduit et différence ; il **n'affiche ni la page, ni le cadre, ni la traduction proposée** de chaque zone. Non implémenté en run25 (voir `LIMITATIONS.md`) |

## 9. Fidélité par document

| Document | Principaux constats | Statut |
|---|---|---|
| DOC-001 | logos intacts ; 5 titres surlignés traduits ; 2 débordements refusés | `REVIEW_REQUIRED` |
| DOC-002 | 1 entité protégée modifiée ; 1 refus « encre résiduelle » ; planche non rouverte en run25 | `REVIEW_REQUIRED` |
| DOC-003 | français conservé ; aucune alerte critique ; aucune référence humaine | `REVIEW_REQUIRED` |
| DOC-004 | cases intactes (alertes moteur maintenues) ; bordures restaurées, 1 filet aminci ; 14 débordements et 3 refus d'encre (source conservée) ; numéros RTL conservés en original ; 20 traductions sur OCR faible | `REVIEW_REQUIRED` |
| DOC-005 | glyphe restauré ; 1 refus d'encre ; français conservé (48 blocs) | `REVIEW_REQUIRED` |
| DOC-006 | 16 pages ; alertes d'entités et 12 masques trop grands (`VISUAL_MASK_TOO_LARGE`) ; 3 330 px d'encre effacée | `REVIEW_REQUIRED` |
| DOC-007 | cases et filet préservés ; 8 débordements et 3 refus d'encre ; tableau réel non relié (`UNMAPPED_TABLE_CONTENT`) ; 23 traductions sur OCR faible | `REVIEW_REQUIRED` |
| DOC-008 | cachet, signature et certification intacts ; français non retraduit ; numéros RTL conservés en original ; 46 bandes localisées | `REVIEW_REQUIRED` |

Aucun document n'est déclaré fidèle ni conforme. Le statut `REVIEW_REQUIRED` est justifié pour chacun par une alerte
critique, une zone non reconstruite ou l'absence de référence humaine.
