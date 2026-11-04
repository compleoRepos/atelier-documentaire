# Note pour le comité : atelier documentaire, LOT 2.3 (4 novembre 2026)

**En une phrase.** Le moteur documentaire reconnaît désormais les **24 langues officielles de l’Union européenne et l’arabe**, son RAG dispose d’une base terminologique et juridique européenne vérifiable, et rien n’a régressé pour l’existant. **La mise en production reste NO-GO** : il manque la relecture humaine, le moteur de traduction cible et la licence des poids OCR.

## 1. Ce qui a été fait

| Chantier | Résultat |
|---|---|
| Audit qualité, performance, robustesse (Phase A) | Chemin réel mesuré de bout en bout (API, file de tâches, stockage, OCR Surya, moteur de traduction). 21 constats classés : 18 défauts ou observations, dont 4 critiques, et 3 constats sur la méthode de mesure. |
| Corrections (Phase B) | 6 défauts de l’audit et la limitation du RAG à 5 langues corrigés, chacun prouvé par des tests qui échouent avant et réussissent après : perte silencieuse de blocs, délai moteur figé, tâches perdues sans alerte, terme de glossaire manqué, ralentissement OCR caché (×3,3), rechargement du tokenizer (environ 4 s par document), RAG limité à 5 langues. |
| Langues | Le produit ne reconnaissait que **7 langues** : pour 18 langues de l’UE, le RAG ne pouvait rien apporter. Il reconnaît maintenant les 24 langues de l’UE et l’arabe, et classe les documents dans ces langues. |
| Base de contenu du RAG | EuroVoc 4.24 (thésaurus officiel de l’UE, 20 537 lignes, 23 langues vers le français) ; 25 textes du droit du travail de l’UE en 24 langues (11 208 articles) ; 1 654 définitions légales alignées ; 290 termes arabes. Sources officielles ou libres, licences vérifiées. |
| Gouvernance | Tout entre en brouillon. Publication à **quatre yeux** (deux personnes distinctes), activation explicite, traçabilité de chaque import. Le RAG reste désactivé par défaut. |

## 2. Les chiffres qui comptent

| Indicateur | Valeur |
|---|---|
| Tests automatiques du backend | **1 207 réussis, 0 échec** (175 de plus qu’à l’audit, aucun supprimé) |
| Parcours complet par langue (envoi, analyse, langue, RAG, moteur) | **24 langues sur 24**, plus un témoin français |
| Langue juste sur des textes officiels jamais vus (18 langues ajoutées) | **95,1 %** ; 100 % sur les paragraphes longs ; 86,4 % sur les fragments courts |
| Langues historiques (fr, en, de, it, es, nl) | **2 229 paragraphes sur 2 229 inchangés** |
| Corpus bancaire Maroc/MRE (646 documents à texte) | **langue et classement identiques** à l’existant |
| Exactitude du contenu RAG (deux évaluateurs automatiques) | définitions 99,1 % ; EuroVoc 95,9 % ; arabe 97,0 % |
| Lecture OCR (Surya), une page par langue | **24 langues de l’UE sur 24 à F1 ≥ 0,95** (moyenne 0,994) ; arabe 0,945 |

## 3. Indice de confiance (≥ 92 % demandé)

Règle fixée avant les mesures : chaque composante doit dépasser 92 % **en borne basse** (intervalle de confiance à 95 %), pas en moyenne. **La plus faible borne basse est de 93,3 %** (exactitude d’EuroVoc). L’objectif est donc atteint pour l’affirmation : « toutes les langues de l’UE et l’arabe sont prises en charge, y compris par le RAG, le contenu est exact, et rien n’a régressé ».

Ce que cet indice **ne dit pas** : il ne mesure pas la qualité des traductions (le moteur cible n’est pas disponible), il ne remplace pas la relecture humaine, qui reste obligatoire quel que soit le score, et il n’autorise pas la production.

## 4. Limites présentées sans les atténuer

- **Aucune relecture humaine** du contenu RAG n’a encore eu lieu. Les deux évaluateurs automatiques sont des modèles de langue ; ils se trompent aussi.
- **Fragments courts** (titres, cellules de tableau) : 86,4 % de langue juste dans les langues ajoutées. En cas de doute, le bloc reste « langue inconnue ». L’irlandais (90,8 %) et le slovène (91,7 %) sont les deux langues les plus faibles.
- **Gain du RAG sur la traduction : non mesuré.** Il faudra le moteur cible et des relecteurs.
- **12 défauts de l’audit restent ouverts**, dont 2 critiques : la reconstruction des tableaux scannés et le découpage des très longs documents (200 pages).
- **CI rouge** sur deux audits de dépendances (bibliothèque d’images Pillow, outillage frontend). Les correctifs sont des montées de version majeure, à qualifier dans une branche dédiée.
- **OCR contrôlé sur une page propre par langue**, pas qualifié : les scans dégradés, l’orientation et les tableaux scannés restent à mesurer.
- **IATE**, la grande base terminologique de l’UE, n’est pas intégrée : son export exige un compte EU Login. Un convertisseur est prêt.

## 5. Décisions demandées au comité

1. Désigner les **deux relecteurs** (soumission et validation) et les premières paires de langues à publier.
2. Fournir un **export IATE** ciblé (travail, banque, finance) avec un compte EU Login, si l’intégration est souhaitée.
3. Fixer le **délai et le plafond** du moteur de traduction cible, et en donner l’accès pour mesurer le gain réel.
4. Valider l’ordre de la suite : mise à jour Pillow et requalification, golden OCR avec tableaux, reconstruction des tableaux, découpage des longs documents.
5. Autoriser, ou non, le **LOT 3** (recherche juridique dans les textes européens chargés) et l’**ouverture publique** du dépôt.

**Statut des dépôts.** Deux dépôts privés. Le travail est sur des branches dédiées avec des demandes de fusion en brouillon, sans fusion ni déploiement. Tous les commits sont au nom de Hamza NORDINE.
