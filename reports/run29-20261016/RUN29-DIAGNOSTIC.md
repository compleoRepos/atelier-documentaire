# RUN29 — Diagnostic reproductible et causes racines

> Périmètre : DOC-001 à DOC-008 (8 originaux autorisés, 31 pages, 1 072 blocs). Aucun extrait, identifiant de bloc, coordonnée, nom de fichier ni empreinte réelle n'est publié ; seuls les identifiants DOC-00x, les numéros de page, les compteurs et les codes d'anomalie le sont.

## 1. État de départ établi avant toute modification

| Élément | Valeur constatée | Preuve |
|---|---|---|
| Code de départ | tête RUN28 `0198654` (code AST-identique au code mesuré RUN28) | empreinte de code du rejeu `run29a` = arbre `0198654` |
| Référence de rendu | `run28e` (verdict RUN28) | rejeu `run29a` sur `0198654` avec la mémoire `run28e` : 0 requête, 0 statut changé, 0 traduction différente, **31/31 aperçus pixel-identiques**, mêmes codes critiques |
| Score officiel de départ | v2 `doc-confidence-2` corpus **65,7063** [90,2433], plafond 75,4630 ; v1 73,9 | règle RUN28 `08e998169c0dad9b` et règle RUN29 finale `4d6b306029f8745b` reproduisent toutes deux la valeur publiée |
| Défauts critiques de départ | scorecard-2 dédupliqués **42**, tous de rendu ; alertes produit `severity=critical` **80** | export anonymisé RUN28 |
| Statuts de départ | TRANSLATED 500, NOT_TRANSLATABLE 141, UNCERTAIN `ocr_unreliable` 137, FAILED `model_returned_source` 84, FAILED `render_overflow` 14 | registre de couverture `run28e` |
| Validation humaine | 0 ligne revue sur 1 072 | pack de revue privé, état NOT_STARTED |

### Les tests prouvent-ils une vraie inférence ?

| Exécution | Ce qui est réellement exécuté | Moteur de traduction |
|---|---|---|
| Suite backend (unit, integration, e2e, regression, security) | code applicatif complet ; moteurs **factices identifiés comme tels** dans les tests de traduction | aucun appel réseau |
| Golden (8 originaux) | analyse, OCR, segmentation, registre, reconstruction et mesures complets sur les 8 originaux | moteur `offline` : **aucun modèle invoqué** (`model_invoked=False`), texte inconnu jamais traduit |
| Rejeux corpus `run29a`…`run29j` | pipeline complet sur les 8 originaux | **mémoire de traduction** revalidée (traductions Interim issues des inférences RUN25–RUN28) : 0 requête ; ces rejeux prouvent le rendu, pas la traduction |
| Passes `run29oss`, `run29oss2`, `run29oss3` | pipeline complet sur les originaux | **vraies inférences** gpt-oss-20b local (127.0.0.1), sans mémoire |

Conséquence : en RUN29, aucune nouvelle inférence Interim n'a été nécessaire ni réalisée sur les originaux ; toute amélioration de traduction revendiquée pour Interim serait fausse. Les gains RUN29 portent sur le rendu, la détection et le moteur privé.

## 2. Tableau initial des défauts (reproduits sur le code et les sorties actuels)

| N° | Document(s) | Défaut | Étape responsable | Gravité | Preuve reproductible | Correction | Test de non-régression |
|---|---|---|---|---|---|---|---|
| D1 | DOC-001, 002, 004, 006, 007, 008 | Triplet `RENDER_SOURCE_TEXT_MISSING` / `RENDER_TEXT_CLIPPED_OR_MISSING` / `RENDER_TRANSLATED_TEXT_MISSING` | reconstruction scan (cible non placée) | critique | 24 blocs traduits non placés dans `run28e` : 14 débordements, 4 masques jugés dangereux, 3 encres résiduelles, 3 scripts RTL non façonnables | traiter les causes D2–D4 ; le triplet reste un **effet** | dérivé (mesuré par le scorer) |
| D2 | DOC-001, 004, 006 | Cible arabe/hébraïque refusée au rendu (`RTL_SHAPING_UNSUPPORTED`) | reconstruction scan | majeur | refus déterministe de toute cible contenant un caractère RTL (primitive de texte sans façonnage) ; 3 blocs | **non corrigé** (OI) | — |
| D3 | DOC-004 | `PROTECTED_REGION_CHANGED` sur 3 cases à cocher (×2 sources : produit et scorer) | masquage | critique | seule la dernière colonne de pixels d'aperçu de chaque case change : la couverture papier commençait à moins d'un pixel d'aperçu du bord de la case | **F43** : dégagement de 1 pt entre couverture et zone protégée, appliqué seulement si la bande est prouvée vierge | `test_run29_layout_regressions.py` (cas F43, dont contre-épreuve) |
| D4 | DOC-004, 006, 007, 008 | 14 blocs `LAYOUT_OVERFLOW` (traduction non placée) | reconstruction scan (repli de taille) | critique | 3 causes mesurées : (a) repli deux lignes calculé à taille nominale qui sort de la boîte alors que deux lignes à 0,72–0,85× tiennent entre les voisins ; (b) hauteur de cadre une ligne insuffisante à l'interligne par défaut ; (c) vrai allongement ×1,7–2,4 dans des cellules de 5,5 pt | **F44** (deux lignes réduites bornées par les voisins les plus proches, espace prouvé vierge) ; **F45** (interligne serré 1,0 en dernier recours) ; (c) non corrigeable sans perte : reste en échec explicite | cas F44 et F45 (scènes synthétiques, contre-épreuves) |
| D5 | DOC-004, 006 | Filet de tableau effacé sous une couverture (révélé par l'inspection d'un placement F44) | masquage (détection de filets F38) | critique | filet incliné de moins de 1° avec un trou de numérisation de 2 px : continuité mesurée 0,77 < seuil 0,85 → filet non reconnu → couverture posée dessus | **F48** : pont des trous de ≤ 3 px (zoom 2) pour le seul test de continuité | `test_run29_render_regressions.py` (cas F48) |
| D6 | DOC-004, 006 | Aucune métrique ne détectait un filet effacé : le défaut D5 faisait **baisser** les alertes | évaluation | critique | contrôle structurel hors ligne : 10 filets effacés dans `run28e` comme dans `run29a`, 11/11 signalements confirmés numériquement, 7 visuellement, 0 faux positif observé ; rappel non mesuré | **F49** : `RENDER_RULE_ERASED` (critique) dans `render_metrics` | cas F49 dont 2 de bout en bout et contre-épreuve |
| D7 | DOC-004 | Faux positif introduit par F48 : le fût d'une lettre grasse dans une couverture courte pris pour un filet | masquage | majeur | couverture rognée à tort sur un titre gras ; disparaît si le pont est limité aux filets vérifiés sur ≥ 20 pt | **F48b** | test F48 (cas court) |
| D8 | DOC-001, 004, 005, 006 | Glyphes source coupés par une couverture trop petite : moitiés de mots, chiffres, lettres de tampon, bas d'un logo visibles à côté de la traduction | masquage + évaluation (aucune métrique) | critique | 13 cas étiquetés visuellement ; trois critères simples rejetés (ne séparent pas) ; critère « fragment orphelin hors de toute boîte OCR » retenu ; puis composantes majoritairement effacées dont un reste est visible | **F50** (fragments orphelins), **F50b** (fragments de filets exclus, laissés à F49), **F50c** (composantes effacées ≥ 50 % avec reste visible) : placement refusé, pixels d'origine conservés, `SCAN_COVER_CUTS_SOURCE_GLYPHS` critique | cas F50, F50b et F50c (contre-épreuves) |
| D9 | DOC-002 | Valeur **manuscrite** lue par l'OCR avec une confiance d'environ 0,2 et traduite en phrase inventée | validation OCR (preuve lexicale) | critique (sens) | un seul mot courant de 4 lettres suffisait à juger le bloc « lexicalement soutenu » | **F51** : sous 0,35 de confiance, un seul mot connu de ≤ 5 lettres n'est pas une preuve → revue humaine, original conservé | `test_run29_ocr_regressions.py` (4 tests, dont contre-épreuve) |
| D10 | moteur privé | Le contrôle préalable du moteur privé plantait (dépendance `jinja2` absente) | inférence (préflight) | bloquant | reproduit avec le vrai tokenizer gpt-oss | **F46** : dépendance déclarée + toute erreur de préflight = anomalie critique sans appel réseau | `test_run29_private_engine.py` |
| D11 | moteur privé | Comptage de jetons faux avec `transformers` 5 (objet `BatchEncoding` au lieu d'une liste) | inférence (budget 32K) | bloquant | reproduit avec le vrai tokenizer ; un type indéterminé n'était pas refusé | **F47** : lecture de `input_ids`, refus fail-closed de tout type inconnu | `test_run29_private_engine.py` |
| D12 | moteur privé | Requêtes de 121 à 334 blocs rejetées en bloc (JSON invalide, cardinalité) → 605 blocs `MODEL_CALL_FAILED` | inférence (découpage) | critique | plafond de 40 blocs et redécoupage borné réservés au mode Interim | **F52** : même politique pour le moteur privé | `test_run29_private_chunking.py` (5 tests ; contre-épreuve : 4/5 échouent sur l'ancien code) |
| D13 | moteur privé | Traçabilité : libellé `private-qwen-gateway` pour gpt-oss ; sans alias, le serveur local renvoie un chemin local comme modèle servi | provenance | majeur | constaté dans les sorties privées (jamais exportées) | alias de modèle imposé côté serveur ; libellé : **non corrigé** (OI) | — |
| D14 | DOC-001, 002, 004, 005, 006, 007, 008 | 84 blocs `model_returned_source` (le modèle renvoie la source) | traduction | majeur | 60/84 de 1 à 3 mots ; 15 à confiance OCR < 0,6 | **non corrigé** (OI) | — |
| D15 | DOC-004 | Défauts préexistants : traduction chevauchant un numéro de liste ; ponctuation bidi inversée ; phrases RTL scindées par lignes OCR ; ligne OCR bruitée traduite incohérente | reconstruction / segmentation / OCR | majeur à critique | inspection visuelle privée | **non corrigés** (OI) | — |
| D16 | DOC-004 | Texte traduit dessiné **à travers** un filet de tableau conservé (aspect barré) ; un cas préexistant RUN28 (bloc à cheval sur deux rangées, texte de la rangée suivante fusionné) et un cas nouveau, rendu visible par F48 qui conserve désormais le filet | reconstruction scan (cadre OCR gonflé ; les contrôles d'espace ne regardaient que l'extérieur de la boîte) | critique | évaluateur géométrique privé sur le rendu final : 6 cadres signalés, étiquetés visuellement 2 vrais, 2 mineurs/ambigus, 2 faux positifs | **F53** : refus du placement si un filet resté visible traverse le corps des lettres (entre 0,1 et 0,5 corps au-dessus de la ligne de base) ; un filet à la ligne de base (effet souligné) reste admis ; original conservé, `SCAN_TEXT_CROSSES_RULE` critique | `test_run29_rule_crossing.py` (contre-épreuves) ; au rejeu : **2/2 vrais refusés, 0/4 autres touchés** |
| D17 | DOC-004 | Un trait de signature lu par l'OCR comme deux lettres, reportées dans la traduction ; la couverture empiète sur le haut du paraphe | OCR + masquage | critique (élément protégé) | inspection visuelle privée : identique en RUN28 et en RUN29 | **non corrigé** (OI) | — |

## 3. Causes racines par étape

| Étape | Causes racines confirmées | Correctifs RUN29 |
|---|---|---|
| Extraction / OCR | preuve lexicale trop faible acceptée à très basse confiance | F51 |
| Segmentation | phrases RTL scindées en lignes OCR (préexistant) | aucun |
| Traduction (moteur privé) | préflight fragile ; comptage de jetons ; absence de découpage borné | F46, F47, F52 |
| Validation | inchangée (gardes d'entités efficaces : une modification d'entité protégée bloquée pendant la passe gpt-oss) | — |
| Masquage | marge sub-pixel autour des zones protégées ; détecteur de filets sensible aux trous de numérisation ; couvertures trop petites qui coupent des glyphes ; signature non reconnue comme zone protégée (ouvert) | F43, F48, F48b, F50, F50b, F50c |
| Reconstruction | replis de taille incomplets pour les lignes uniques ; cadre gonflé traversant un filet conservé ; façonnage RTL absent | F44, F45, F53 ; RTL ouvert |
| Évaluation | filets effacés, glyphes coupés et texte barré par un filet invisibles des métriques | F49 (métrique) ; F50/F50c et F53 (refus explicite + anomalie critique) |

## 4. Ce que le diagnostic change dans la lecture des scores

RUN28 ne comptait ni les filets effacés ni les glyphes source coupés. Ces défauts existaient déjà (`run28e` contient les mêmes 10 filets effacés que `run29a`). RUN29 les rend visibles ou les refuse. Une partie de la hausse des défauts critiques et de la baisse de couverture est donc le **prix de la vérité**, pas une dégradation du rendu ; la démonstration chiffrée figure dans [RUN29-BEFORE-AFTER.md](RUN29-BEFORE-AFTER.md).
