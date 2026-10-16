# RUN18 — Analyse des causes racines des régressions run17

Branche : `feature/run18-regressions-20261011`. Code de départ : `ebb09eb` (identique à l'archive
`atelier-documentaire-prive-ebb09eb-code.zip`, vérifié par `diff -rq`). Toutes les données sont des
compteurs anonymisés ; aucun texte, nom, identifiant ni empreinte des originaux n'est versionné.

Passage retenu comme **verdict run18** : `run24` (empreinte du code `4d4956273c97d866`, voir §7). Les
passages intermédiaires (run18a, run19, run20, run21, run22, run23) sont conservés en privé et cités quand ils
expliquent une décision ; ils ne sont pas présentés comme résultat final.

## 1. Méthode suivie (prompt §2)

| Étape | Réalisation | Preuve (privée, hors Git) |
|---|---|---|
| Inspecter le code exact | archive code == `ebb09eb` (`diff -rq` vide) | journal run18 |
| Lire rapports, métriques, rendus run17 | rapports `reports/final-20261009/*`, `metrics-run17-final.json`, planches run17 | archive preuves 09/10 |
| Baseline immuable | copie en lecture seule de la baseline 08/10, de run17 et des analyses run10, manifeste SHA-256 (1 527 fichiers) | `baseline-immutable.sha256` |
| Tests existants sur le code inchangé | suite technique exécutée **avant** toute modification | `pytest-baseline-code.log` |
| Reproduire bloc par bloc | outil `diag_blocks` + mesure indépendante du PDF rendu (`tools/recette/render_outcome.py`) sur baseline et run17 | `diag/DOC-00x-run17.{txt,json}` |
| Plan priorisé | DOC-004, DOC-005, DOC-007, puis DOC-001, DOC-002 ; non-régression DOC-006, DOC-008 | journal run18 |

## 2. Audit des métriques avant toute optimisation (prompt §3 et §9)

Les chiffres du rapport précédent ont été recalculés depuis les fichiers bruts. Quatre défauts de **mesure**
expliquent une partie des « régressions » ; ils ont été corrigés dans un outil v2 appliqué **à l'identique**
à la baseline, à run17 et à run18 (`tools/recette/measure_v2.py`).

| Défaut de mesure | Effet observé | Correction v2 |
|---|---|---|
| Langue par bloc lue dans l'analyse **de chaque run** (détecteurs différents) | dénominateurs non comparables entre baseline et run17 | langue recalculée sur le texte source, même fonction pour tous les runs |
| Réécriture d'un bloc **français** comptée comme « traduite » | baseline de DOC-005 créditée de réécritures hors périmètre | périmètre « attendu » indépendant du run ; réécritures comptées à part (`changed_outside_expected`) |
| « Écrit » = 3 premiers mots de la cible n'importe où sur la page | une traduction coupée comptait comme écrite | rappel des mots de la cible dans les mots insérés **près du bloc** (WRITTEN ≥ 0,85, PARTIAL ≥ 0,25, sinon ABSENT) |
| « Coupés ou manquants » = somme de 3 codes portant le même compte | 195 = 65 × 3 et 276 = 92 × 3 : triple comptage | un défaut par bloc, mesuré dans le PDF de sortie |
| Débordement baseline (6) vs run17 (35) | la baseline réduisait ou tronquait **sans signaler** | débordement/coupure mesurés dans la sortie, même méthode pour tous |

Conséquence importante : la baisse « 42,44 % → 8,28 % » de DOC-005 est un **artefact de dénominateur**
(document français ; libellés français courts détectés comme néerlandais ou espagnol ; bruit OCR d'un
caractère ; noms et identifiants). Ce n'est pas une omission de traduction.

**Correction v2.1 de la mesure (M1).** L'audit visuel de DOC-008 a montré un biais de la v2 : la zone de
recherche des mots insérés d'un bloc s'étendait de 3 pt à gauche mais d'une demi-largeur à droite. Avec F5
(ancrage à droite des blocs RTL, croissance vers la gauche), une traduction complète écrite à gauche du
bloc était comptée PARTIAL. La v2.1 rend la zone **symétrique**, pour tous les runs. Contrôle : la baseline et
run17 (qui ne croissaient pas vers la gauche) donnent **exactement** les mêmes chiffres en v2 et en v2.1 ;
seul run18 change. Test synthétique `test_recette_render_outcome.py` (croissance gauche, débordement droit,
troncature réelle ; échoue sur l'ancienne zone). Identifiant de méthode : `measure-v2.1-run18`.

## 3. Causes racines confirmées des régressions run17

Les pertes sont exprimées en caractères source de blocs écrits en baseline et non écrits en run17
(mesure indépendante du PDF, définitions §2).

| # | Symptôme run17 | Documents (car. perdus) | Cause confirmée | Composant / fonction |
|---|---|---|---|---|
| C1 | traductions écartées par la garde d'encre (D20) | DOC-007 1 058, DOC-004 272, DOC-006 67 | des **mots réels** (« de », « (2) », « en ») isolés de leur ligne par la règle run10 des mots hauts : leur boîte Tesseract couvrait deux lignes imprimées ⇒ bloc orphelin de 6×14 pt ⇒ (a) la ligne perdait ces mots, (b) les masques des voisins étaient rétrécis, l'encre source restait visible et la garde D20 écartait la traduction | `app/ai/ocr/tesseract.py::split_line_at_gaps` |
| C2 | blocs de formulaire conservés en source | DOC-004 305, DOC-006 301, DOC-007 147, DOC-001 140 | la segmentation fusionnait des lignes de cellules ou rangées différentes ; la garde de structure (D16) protégeait alors **tout** le bloc | `segmentation.py` (fusion), `line_verification.py` (garde) ; lignes « libellé \| valeur » lues comme une seule ligne OCR à travers un filet vertical |
| C3 | débordements, cellule absente | DOC-004 617, DOC-007 285, DOC-008 97 | DOC-004 : le français est ~2× plus long que les libellés arabes ; le cadre ne grandissait **que vers la droite**, alors que l'espace libre d'une cellule arabe alignée à droite est **à gauche** | `pdf_fidelity.py::_plan_scan_block` (croissance), `_scan_style` (alignement mesuré sur le bord gauche) |
| C4 | libellés arabes courts restés en arabe | DOC-004 241 (18 libellés) | renvoyés inchangés par Interim ; la reprise unique (D8) exigeait ≥ 2 mots de ≥ 4 lettres ⇒ jamais relancés | `app/ai/translation/service.py::_retry_candidate` |
| C5 | DOC-005 « non français » | DOC-005 (périmètre) | détection de langue par bloc non fiable sur les libellés français courts | `segmentation` (détection), absence de preuve lexicale |
| C6 | DOC-002 conservé en source | DOC-002 206 | garde d'entités (D26) : la sortie modifiait une entité protégée ⇒ source conservée (comportement voulu, signalé) | `service.py::_restore_and_validate` |
| C7 | défauts de mesure | tous | voir §2 | `tools/recette/measure_corpus_metrics.py` |

Défauts **nouveaux** trouvés par les audits visuels des passages run18 successifs (planches et zooms
privés), corrigés avant le verdict :

| # | Passage | Symptôme | Cause confirmée | Composant / fonction |
|---|---|---|---|---|
| R18-A | run18a | liste numérotée 2 à 7 reflowée en paragraphe : libellés désalignés des montants voisins | lignes d'items énumérés regroupées en un paragraphe | `line_verification.py` (nouvelle scission) |
| R18-B | run18a | case à cocher « non + case » remplacée par un mot traduit | la case vide était lue comme une lettre (OCR conf. 0,94) puis masquée avec le libellé | `line_verification.py` (détection de cases) |
| R18-C | run18a | coupure intra-mot dans une cellule étroite | `insert_textbox` coupe un mot plus large que le cadre ; le repli `SINGLE_LINE_WRAPPED_INTO_BLANK` l'acceptait | `pdf_fidelity.py::_fit_on_scratch` |
| R18-D | run18a | numéro de téléphone avec parenthèses inversées « )chiffres( » | parenthèses miroir produites par l'OCR sur une ligne droite-à-gauche | `line_verification.py` (normalisation) |
| R18-E | run19 | deux options « case + oui, … » fusionnées en un paragraphe reflowé sur les deux cases | une ligne par option, mais regroupées par la segmentation | `line_verification.py` (scission par case) |
| R18-F | run19 | jeton OCR de la case (« © », « O », « E »…) envoyé et traduit | la case est lue comme une lettre en tête de ligne | `line_verification.py` (retrait du jeton) |
| R18-G | run19 | libellé renvoyé inchangé classé « protégé conservé » | l'évaluation traitait une case automatique comme protection de tout le bloc, contrairement au rendu | `pipeline.py::_protected_for` |
| R18-H | run19/run18a | 348 blocs sur 1 064 (70,6 % des caractères) avec une cible Interim **différente à source identique** | variance de génération du moteur temporaire ; rend toute comparaison entre passages non attribuable au code | lanceur de corpus (`tools/interim_owner_corpus_run.py`) |
| R18-I | run20 | faux `UNMAPPED_TABLE_CONTENT` sur DOC-005/006/007/008 | la mémoire de traduction retirait de l'IR réduit les blocs servis par le cache, mais laissait leurs tableaux sans membres | `interim_owner_corpus_run.py` (élagage) |
| R18-J | run21 | trois cases d'option vides et une case « oui » effacées (DOC-004 p. 1) ; « case + oui » traduit comme un nom propre | boîtes de ligne OCR arabes gonflées (58–66 px à l'échelle d'analyse pour des cases de 27–29 px) : la borne « hauteur ≥ 0,6 × ligne » rejetait des cases par ailleurs parfaites (contour plat, 4 coins, isolée) | `line_verification.py::checkbox_glyphs` |
| R18-K | run22 | option « case + oui » d'un champ de formulaire traduite par un faux sens | après retrait du jeton de case, la ligne OCR restait dégradée (mots arabes manquants + jetons latins courts parasites) ; le modèle comblait les trous | `line_verification.py::strip_checkbox_tokens` |
| R18-L | run23 (présent dès run17) | deux lignes d'un même paragraphe imprimées l'une sur l'autre (DOC-007 p. 3 : 26 mots en collision ; 29 en run17, 0 en baseline) | les boîtes OCR de deux lignes consécutives se chevauchaient de 2 pt ; un voisin chevauchant était **retiré** des obstacles, la traduction plus longue du bloc inférieur grandissait vers le haut sur la ligne du bloc supérieur, elle-même redessinée | `pdf_fidelity.py::_plan_scan_block` (obstacles) |

## 4. Correctifs (défaut, cause, fonction corrigée, preuve)

Chaque correctif est une règle technique générale (aucun contournement fondé sur un nom de fichier ou un
identifiant de document) et porte au moins un test synthétique (`backend/tests/unit/test_run18_regressions.py`,
39 tests ; `test_recette_render_outcome.py`, 2 tests).

| Id | Défaut initial | Fonction corrigée | Règle | Tests | Preuve corpus |
|---|---|---|---|---|---|
| F1 | C1 mots réels isolés | `tesseract.py::split_line_at_gaps` | un mot anormalement haut reste dans sa ligne ; seule sa hauteur est plafonnée à la bande des autres mots (`tall_words_clamped`) | `test_real_word_with_a_two_line_box_stays_in_its_line_run18` + test d'isolement adapté | rapport de régression §3 |
| F2b | C2 « libellé \| valeur » en une ligne | `tesseract.py::vertical_rule_between` | découpe d'une ligne OCR à un filet vertical sombre (≥ 92 % de la bande) entre deux mots ; glyphes de filet supprimés (`split_at_rule`) | 2 tests | idem |
| F2 | C2 bloc multi-rangées préservé | `line_verification.py::split_block_at_rules` | un bloc dont des lignes sont séparées par un filet horizontal est scindé (`<id>-rN`), références de tableaux/avertissements remappées | 3 tests + test D16 adapté | idem |
| F3 | C4 libellés non latins renvoyés inchangés | `service.py::_retry_candidate` | reprise unique aussi pour un mot en écriture non latine (la cible française est latine) et pour un mot étranger courant (`foreign_word_evidence`) | 2 tests | idem |
| F4 | C5 langue par bloc | `language_evidence.py` (nouveau), appelé par `verify_lines` | preuve lexicale hors ligne (wordfreq) : couverture de mots courants, mots rares partout (noms) exclus ; bloc sans mot ⇒ `NO_LINGUISTIC_CONTENT_KEPT` (non envoyé) | 3 tests | calibration : 10 relabellisations, toutes correctes à la revue |
| F5 | C3 croissance à droite seulement | `pdf_fidelity.py::_plan_scan_block`, `_grow_left`, `_ink_obstacles`, `_growth_is_blank`, `_scan_style` | aligné à droite ⇒ croissance à gauche ; centré ⇒ symétrique ; source RTL dominante ⇒ ancrage à droite ; contrôle d'encre identique | 3 tests | idem |
| F7 | §10 statuts absents | `block_status.py` (nouveau), `pipeline.translate_document` | statut explicite par bloc (TRANSLATED, PRESERVED_INTENTIONALLY, NOT_TRANSLATABLE, UNCERTAIN, FAILED, NOT_PROCESSED) + raison | 3 tests | rapport de couverture §4 |
| F9 | R18-B case masquée | `line_verification.py::checkbox_glyphs`, `_isolated`, `_declare_checkbox_regions` ; `protected_visuals.py::carves_only` ; `pdf_fidelity.py::_scan_region_protects` | composante carrée, quatre profils extérieurs plats, quatre coins encrés, séparée du libellé par un espace ; déclarée région protégée `checkbox_glyph` (état vide/cochée/pleine) ; elle **découpe** le cadre du texte et les masques sans protéger tout le bloc | 7 tests | calibration : 22 cases détectées (DOC-004), faux positif DOC-007 éliminé par le critère d'isolement |
| F10 | R18-A liste reflowée | `line_verification.py::split_block_at_enumerators` | ≥ 3 lignes portant une énumération strictement consécutive (début ou fin de ligne) ⇒ un bloc par item, lignes de continuation rattachées à leur item (`<id>-iN`) | 5 tests | 1 bloc scindé dans le corpus (le cas observé) |
| F11 | R18-D parenthèses miroir | `line_verification.py::normalize_mirrored_brackets` | uniquement sur une ligne contenant des lettres RTL, « )chiffres( » ⇒ « (chiffres) », tracé | 1 test | 1 correction dans le corpus |
| F12 | R18-C coupure intra-mot | `pdf_fidelity.py::_longest_word_fits` dans `_fit_on_scratch` | un ajustement est refusé si un mot ne tient pas sur une ligne du cadre ; sinon cadre plus large, police plus petite (plancher 72 % inchangé) ou débordement signalé | 1 test | zoom DOC-004 : plus de coupure intra-mot |
| F13 | R18-E options fusionnées | `line_verification.py::split_block_at_checkboxes` | bloc dont ≥ 2 lignes commencent sur une case (bord de lecture : gauche en LTR, droite en RTL, tolérance 1,5 pt) ⇒ un bloc par option (`<id>-oN`) | 1 test | 1 bloc scindé (DOC-004 p. 2) |
| F13b | R18-F jeton de case traduit | `line_verification.py::strip_checkbox_tokens` | jeton ≤ 2 car. en tête suivi de mots ⇒ retiré (`ocr_text_raw` conservé) ; case fusionnée au mot ⇒ 1er car. retiré seulement si le reste est un mot fréquent d'une langue principale du document ; sinon ligne `fused_unreliable` ⇒ bloc `ocr_unreliable` (UNCERTAIN, non envoyé, source conservée) | 3 tests | 17 lignes d'option traitées (DOC-004) |
| F15 | R18-G faux « protégé » | `pipeline.py::_protected_for` | une case automatique (`carves_only`) ne protège jamais un bloc dans l'évaluation, comme au rendu ; un libellé renvoyé inchangé redevient une erreur visible | 1 test | DOC-004 : 2 libellés reclassés |
| F16 | R18-H variance Interim, R18-I faux UNMAPPED | `interim_owner_corpus_run.py` (`--translation-cache`, `_send_signature`, `_table_has_members`, `_cached_issues_for`) | mémoire de traduction **fermée par défaut** : une cible n'est réutilisée que si la signature du bloc (tout sauf la géométrie/le rendu) est identique ; tout bloc modifié repart vers Interim sous la garde 32K ; un tableau dont tous les blocs sont servis par la mémoire est retiré de l'IR réduit, un tableau réellement sans correspondance reste signalé | `test_translation_memory_prunes_fully_cached_tables_but_keeps_unmapped` | run21 : faux UNMAPPED de run20 supprimé, vrai UNMAPPED DOC-007 conservé |
| F17 | R18-J cases effacées | `line_verification.py::checkbox_glyphs` | sous la borne « 0,6 × hauteur de ligne », une composante reste une case si elle est **vide**, ≥ 1,5 × la hauteur médiane des glyphes de sa ligne et ≥ 0,35 × la ligne ; les composantes pleines (points gras, puces : 0,6–0,9 × le glyphe médian dans le corpus) restent rejetées ; trace `height_reference=line_glyphs` | 2 tests (dont un échoue sans F17) | calibration : 21 composantes rejetées par la seule hauteur, 7 vides (vraies cases) / 14 pleines ; 5 cases nouvelles, toutes vérifiées visuellement, 0 effet sur les 7 autres documents |
| F18 | R18-K faux sens sur OCR dégradé | `line_verification.py::mixed_script_noise`, `strip_checkbox_tokens` | après retrait du jeton de case, une ligne d'option RTL (≥ 4 lettres RTL) portant encore 1 ou 2 jetons latins de ≤ 3 lettres est une lecture dégradée ⇒ bloc `ocr_unreliable` (`checkbox_line_mixed_script_noise`), UNCERTAIN, non envoyé | 2 tests | 17 lignes d'option : 2 reclassées, 0 autre changement ; règle non appliquée hors lignes d'option (elle toucherait 12 lignes sur 1 328) |
| F19 | R18-L lignes superposées | `pdf_fidelity.py::_neighbour_obstacle` dans `_plan_scan_block` | un voisin qui chevauche légèrement le cadre reste un obstacle, rogné à sa partie extérieure (au-dessus, au-dessous ou sur le côté) ; un voisin chevauchant largement sur les deux axes (conteneur, artefact de regroupement) reste ignoré comme avant | 2 tests (dont un démontre la montée sur la ligne voisine avec l'ancienne règle) | run24 : collisions DOC-007 26 → 0, 0 sur les 7 autres documents, codes critiques inchangés |
| M1 | biais de mesure v2 | `tools/recette/render_outcome.py::_zone` | zone de recherche symétrique (§2) | 2 tests | baseline et run17 inchangés en v2.1 |

Aucun seuil de qualité n'a été abaissé, aucune garde de sécurité ou de fidélité n'a été supprimée. Les
gardes D16 (structure), D20 (encre source), D21 (écriture minoritaire), D25 (OCR sans confiance), D26
(entités) restent actives ; F2/F9/F10/F13 réduisent les cas où elles bloquaient un bloc entier à tort, en
corrigeant la segmentation en amont. F13b, F17 et F18 vont dans le sens **fail-closed** : une lecture
douteuse n'est plus envoyée au modèle, elle reste en source avec le statut UNCERTAIN et sa raison.

## 5. Ce que ces corrections ne font pas

* F6 (cible contenant de l'arabe, façonnage RTL) n'a **pas** été implémenté : le comportement reste
  fail-closed (`RTL_SHAPING_UNSUPPORTED`, bloc conservé et signalé).
* F14 (mot ou ligne courte à faible confiance dans une langue absente du document ⇒ UNCERTAIN) n'a pas été
  implémenté en général : la calibration aurait touché des libellés légitimes. F18 en est la seule forme
  retenue, restreinte aux lignes d'option de formulaire où la case prouve une lecture dégradée.
* La détection de cases n'a pas de vérité terrain : le rappel n'est pas mesuré exhaustivement. Les petits
  carrés **pleins** à mi-hauteur de ligne (cases cochées probables, DOC-004) ne sont pas détectés ; ils restent
  dans des blocs non traduits dans le verdict, donc non masqués, mais aucune garantie générale n'existe.
* `UNMAPPED_TABLE_CONTENT` (DOC-007) **n'est pas corrigé** : les deux tableaux candidats sont des cadres
  pleine page détectés sur les bordures de numérisation de deux **versos blancs** (0 bloc OCR, vérifié
  visuellement) ; aucun texte n'est perdu. L'alerte est conservée car le service ne dispose d'aucune mesure
  d'encre de page : il ne peut pas distinguer une page blanche d'une page dont l'OCR a échoué. Piste : mesure
  d'encre par page à l'analyse.
* Les données lexicales wordfreq sont sous licence CC-BY-SA-4.0 (code Apache-2.0) : licence à valider
  avant distribution ; en leur absence, aucune relabellisation n'est faite (comportement antérieur).

## 6. Variance du moteur temporaire Interim

À source identique, run18a et run19 ont reçu une cible différente pour 348 blocs sur 1 064 (33 898 caractères
sur 47 997, 70,6 %). Cette variance rend une comparaison « code A contre code B » non attribuable si les deux
passages appellent le moteur. Mesures prises :

* mémoire de traduction F16 pour les passages de vérification ; chaque bloc dont le contenu envoyé change
  repart vers Interim, avec le même contrôle de budget ;
* expérience contrôlée privée « code run18 + cibles run17 à source identique » (0 requête) pour séparer
  l'effet du code de l'effet du moteur (rapport de régression §4) ;
* les résultats Interim restent identifiés comme tels (`served_model` gpt-5-mini) et ne valent pas validation
  de Qwen.

## 7. Chaîne des passages et verdict

| Passage | Code | Traductions | Rôle |
|---|---|---|---|
| run18a | F1–F7 | Interim, toutes requêtes | premier passage, audit visuel ⇒ R18-A…D |
| run19 | + F9–F12 | Interim, toutes requêtes | référence de la mémoire ; audit ⇒ R18-E…H |
| run20 | + F13, F13b, F15, F16 v1 | mémoire run19 | intermédiaire, faux UNMAPPED (R18-I) |
| run21 | + correctif F16 | mémoire run19 ; 1 requête DOC-004 | audit ⇒ R18-J |
| run22 | + F17 | mémoire run21 ; 1 requête DOC-004 | audit ⇒ R18-K |
| run23 | + F18 | mémoire run22 ; 0 requête | audit ⇒ R18-L |
| **run24** | **+ F19 (empreinte `4d4956273c97d866`)** | mémoire run23 ; 0 requête | **verdict run18** |

Tous les passages ont laissé les 8 originaux inchangés (SHA-256 vérifié avant/après), sans aucune
violation du budget 32 768 tokens ; les 8 documents sont `REVIEW_REQUIRED` dans le verdict.
