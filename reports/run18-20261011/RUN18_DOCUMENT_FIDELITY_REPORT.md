# RUN18 — Rapport de fidélité documentaire

Verdict run18 = passage `run24` (empreinte du code `4d4956273c97d866`). Les planches comparatives
(original / baseline / run17 / run18, diff run18/original, diff run18/run17), l'audit des régions visuelles et
les zooms sont **privés** (ils contiennent les documents) et ne sont pas versionnés ; ce rapport n'en donne
que des compteurs et des constats anonymisés. Mesures : `tools/recette/render_outcome.py` et
`tools/recette/compare_runs_sheets.py`, mêmes règles pour les trois runs.

Les 8 originaux sont inchangés (SHA-256 vérifié avant/après chaque passage). Le nombre de pages est
conservé pour les 8 documents (31 pages au total).

## 1. Structure

| Document | Pages | Tableaux / cellules détectés | Blocs run17 → run18 | Scissions run18 (filet / liste / option) | Repli cellule → blocs (run17 → run18) |
|---|---|---|---|---|---|
| DOC-001 | 2 | 2 / 283 | 47 → 47 | 0 / 0 / 0 | 8 → 8 |
| DOC-002 | 1 | 1 / 1 | 35 → 24 | 0 / 0 / 0 | 2 → 2 |
| DOC-003 | 1 | 0 / 0 | 13 → 13 | 0 / 0 / 0 | 0 → 0 |
| DOC-004 | 2 | 2 / 10 | 225 → 229 | 1 / 6 / 2 | 8 → 12 |
| DOC-005 | 2 | 2 / 2 | 96 → 89 | 0 / 0 / 0 | 4 → 4 |
| DOC-006 | 16 | 10 / 25 | 434 → 418 | 0 / 0 / 0 | 26 → 26 |
| DOC-007 | 5 | 5 / 168 | 222 → 178 | 0 / 0 / 0 | 20 → 18 |
| DOC-008 | 2 | 2 / 797 | 76 → 74 | 0 / 0 / 0 | 8 → 8 |

Les variations du nombre de blocs viennent de F1 (mots réels réintégrés à leur ligne au lieu de former des
blocs orphelins) et de F2/F10/F13 (scissions). Les blocs scindés gardent leurs références de tableau
(remappage F2) ; aucune cellule n'est réordonnée. `PDF_TABLE_STRUCTURE_CHANGED` (DOC-001 en run17) a
disparu en run18.

## 2. Mise en page : débordements, textes coupés, superpositions (même méthode, baseline / run17 / run18)

| Document | `LAYOUT_OVERFLOW` | `SCAN_TEXT_OVER_SOURCE_INK` | Car. absents par débordement | Car. absents par encre résiduelle | Mots en collision | Mots hors page | Blocs sur encre |
|---|---|---|---|---|---|---|---|
| DOC-001 | 0 / 1 / 2 | 0 / 0 / 0 | 0 / 18 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| DOC-002 | 0 / 1 / 0 | 0 / 1 / 0 | 0 / 0 / 0 | 0 / 91 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| DOC-003 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| DOC-004 | 4 / 17 / 13 | 0 / 6 / 8 | 176 / 664 / 455 | 0 / 272 / 345 | 0 / 5 / 0 | 0 / 0 / 0 | 0 / 1 / 1 |
| DOC-005 | 0 / 0 / 0 | 0 / 0 / 1 | 0 / 0 / 0 | 0 / 0 / 88 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| DOC-006 | 0 / 3 / 3 | 0 / 1 / 2 | 0 / 28 / 66 | 0 / 67 / 14 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| DOC-007 | 2 / 11 / 9 | 0 / 16 / 8 | 263 / 408 / 354 | 0 / 1 146 / 732 | 0 / 29 / 0 | 0 / 0 / 0 | 0 / 1 / 1 |
| DOC-008 | 0 / 2 / 2 | 0 / 1 / 0 | 0 / 97 / 193 | 0 / 85 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

Notes de méthode :

* « Car. absents par débordement / encre résiduelle » : caractères de blocs dont la traduction a été
  **refusée et signalée** par le moteur de rendu (le texte source reste visible), mesurés dans le PDF.
* La baseline affiche moins de débordements parce qu'elle réduisait la police ou tronquait **sans le
  signaler** (rapport de causes §2) ; ses chiffres de la colonne « débordement » sont donc un minimum.
* « Mots en collision » : mots insérés dont la boîte recouvre à plus de 30 % celle d'un autre mot inséré.
  Les 29 collisions de run17 (DOC-007) et les 26 du passage run23 relevaient du défaut R18-L (lignes
  voisines superposées), corrigé par F19 ; 0 dans le verdict, sur les 8 documents.
* « Texte coupé » : F12 refuse tout ajustement qui couperait un mot à l'intérieur ; aucune coupure intra-mot
  n'a été observée sur les zooms du verdict.

## 3. Régions graphiques (prompt §13.4)

2 154 régions candidates détectées sur l'original (cachets, logos, signatures, images, graphiques
vectoriels, cases). Une région est « altérée » si plus de 2 % de ses pixels changent par rapport à
l'original.

| Document | Régions (type : nombre) | Altérées baseline / run17 / run18 | Examen visuel du verdict (planches privées) |
|---|---|---|---|
| DOC-001 | cachet/logo : 10 | 0 / 5 / 5 | les 5 régions altérées sont des lettres de titres classées « cachet/logo » par le détecteur, remplacées par leur traduction ; aucun cachet réel touché |
| DOC-002 | image : 110, monochrome : 4, vecteur : 109 | 19 / 12 / 15 | logo d'en-tête, cachet, signature, annotation manuscrite et logos de pied **intacts** ; les régions « image » sont des bandes de lignes de texte du scan, altérées par le remplacement de texte |
| DOC-003 | image : 110, monochrome : 1, vecteur : 109 | 0 / 2 / 2 | identique à run17 |
| DOC-004 | case : 27, monochrome : 3, vecteur : 216 | 7 / 10 / **1** | cases d'option conservées (F9, F13, F17) ; 1 région monochrome altérée près d'un masque de texte |
| DOC-005 | image : 220, monochrome : 3, vecteur : 218 | 4 / 3 / 5 | bandes de texte traduites ; aucun élément graphique effacé |
| DOC-006 | monochrome : 1, cachet/logo : 18 | 0 / 5 / 6 | surlignages de couleur sous des lignes traduites (le texte traduit est écrit sur le fond surligné) ; signature intacte |
| DOC-007 | monochrome : 7, vecteur : 541 | 0 / 2 / 1 | filets et cadres conservés |
| DOC-008 | image : 221, monochrome : 8, vecteur : 218 | 33 / 50 / 48 | bandes de texte d'en-tête traduites ; glyphes de logo centraux intacts |

Les cases détectées (27 sur DOC-004) sont déclarées comme régions protégées `checkbox_glyph` : elles
découpent le cadre de texte sans bloquer tout le bloc. `PROTECTED_REGION_CHANGED` ×8 sur DOC-004 est une
alerte **légitime et nouvelle** (contrôle qui n'existait pas pour ces cases avant run18) ; la différence de
pixels est faible et localisée au bord des masques ; elle reste à la revue.

## 4. Données critiques (prompt §13.5)

| Document | Alerte | Sort dans le rendu | Constat |
|---|---|---|---|
| DOC-002 | `PROTECTED_ENTITY_CHANGED` ×1 | cible rejetée, source conservée | garde d'entités efficace ; le paragraphe reste dans sa langue d'origine |
| DOC-006 | `PROTECTED_ENTITY_CHANGED` ×1 | cible rejetée, source conservée | idem |
| DOC-006 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1 | cible appliquée | date collée par l'OCR (mois+année sans espace) classée comme code ; le mois est traduit ; **valeur exacte** ; alerte conservatrice conservée |
| DOC-006 | `HALLUCINATION_UNIT_CHANGED` ×1 | cible appliquée | longueur en mètres traduite correctement ; l'extracteur d'unités ne reconnaît pas la forme accentuée française (faux positif, déjà présent en run17, voir `LIMITATIONS.md`) |
| DOC-007 | `PROTECTED_ENTITY_CHANGED` ×1 | cible rejetée, source conservée | idem DOC-002 |

Aucune valeur critique (montant, date, identifiant, référence) altérée n'a été constatée dans le rendu du
verdict. Il n'existe pas de référence humaine : ce constat ne vaut pas validation exhaustive.

## 5. Tableaux et champs (prompt §13.6)

* Scissions F2 (filets), F10 (listes), F13 (options) : un bloc par rangée, item ou option ; les libellés
  restent en face de leurs valeurs (zooms DOC-004 : liste numérotée et montants alignés, options en face de
  leurs cases).
* `TABLE_CELL_FALLBACK_TO_BLOCKS` (avertissement) : la cellule est traduite bloc par bloc ; DOC-004 passe de
  8 à 12 parce que les blocs scindés sont comptés séparément.
* `UNMAPPED_TABLE_CONTENT` ×1 (DOC-007) : deux cadres pleine page détectés sur des versos blancs ; aucun
  texte perdu ; alerte conservée (rapport de causes §5).

## 6. Défauts visuels restants (non masqués)

* DOC-002 : un fragment OCR d'**écriture manuscrite** (confiance OCR 0,21) a été envoyé au moteur et sa
  « traduction » est imprimée près de l'annotation manuscrite (baseline et run17 en inséraient aussi à cet
  endroit). Aucun seuil de confiance ne sépare ce cas des titres en gras légitimes lus avec une confiance
  équivalente : non corrigé, voir `LIMITATIONS.md`.
* DOC-004 et DOC-007 : débordements signalés et encre résiduelle sous des masques rétrécis ; le texte source
  reste visible là où la traduction est refusée.
* DOC-001 : 93 caractères dont la cible contiendrait de l'arabe (façonnage RTL non supporté, refus signalé).

## 7. Statut final par document

| Document | Statut | Motifs principaux |
|---|---|---|
| DOC-001 | `REVIEW_REQUIRED` | débordements ×2, structure de formulaire ambiguë, RTL non supporté |
| DOC-002 | `REVIEW_REQUIRED` | entité protégée (source conservée), fragment manuscrit traduit, masques dangereux |
| DOC-003 | `REVIEW_REQUIRED` | aucune référence humaine ; 21 caractères renvoyés inchangés |
| DOC-004 | `REVIEW_REQUIRED` | débordements ×13, encre résiduelle ×8, régions de cases ×8, OCR non fiable |
| DOC-005 | `REVIEW_REQUIRED` | encre résiduelle ×1, retours inchangés |
| DOC-006 | `REVIEW_REQUIRED` | alertes d'entités/unités (valeurs exactes), masques, débordements ×3 |
| DOC-007 | `REVIEW_REQUIRED` | débordements ×9, encre résiduelle ×8, `UNMAPPED_TABLE_CONTENT`, entité protégée |
| DOC-008 | `REVIEW_REQUIRED` | débordements ×2 |
