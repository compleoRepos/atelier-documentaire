# RUN29 — Synthèse

## Verdict

**NO-GO.** Le RUN29 n'est pas apte à une mise en service bancaire ou client. 8/8 documents `REVIEW_REQUIRED`, défauts critiques mesurés sur 7 documents sur 8, **0 ligne humaine revue sur 1 072**, aucun moteur privé qualifié. Score officiel du corpus (borne basse v2, méthode gelée) : **64,4737**, contre 65,7063 au RUN28 ; seuil de 94 non atteint et inaccessible sans références humaines (plafond 75,4630). Motivation détaillée : [RUN29-DEPLOYMENT-VERDICT.md](RUN29-DEPLOYMENT-VERDICT.md).

## Résultats par document

| Document | Pages | v2 borne basse RUN28 → RUN29 | Défauts critiques sc-2 | Alertes produit critiques | Blocs traduits et placés | Couverture écrite | Statut | Lignes humaines revues |
|---|---|---|---|---|---|---|---|---|
| DOC-001 | 2 | 62,77 → 60,02 | 3 → 4 | 6 → 8 | 8 → 7 | 51,0 % → 39,6 % | `REVIEW_REQUIRED` | 0/47 |
| DOC-002 | 1 | 66,71 → 66,40 | 4 → 4 | 8 → 8 | 9 → 8 | 64,4 % → 62,8 % | `REVIEW_REQUIRED` | 0/24 |
| DOC-003 | 1 | 62,71 → 62,71 | 0 → 0 | 0 → 0 | 2 → 2 | 74,1 % → 74,1 % | `REVIEW_REQUIRED` | 0/13 |
| DOC-004 | 2 | 67,00 → 65,72 | 19 → 21 | 35 → 42 | 93 → 87 | 64,4 % → 58,3 % | `REVIEW_REQUIRED` | 0/229 |
| DOC-005 | 2 | 53,04 → 47,18 | 0 → 4 | 0 → 8 | 1 → 0 | 9,8 % → 0,0 % | `REVIEW_REQUIRED` | 0/89 |
| DOC-006 | 16 | 73,58 → 73,54 | 5 → 11 | 10 → 22 | 271 → 268 | 94,0 % → 93,9 % | `REVIEW_REQUIRED` | 0/418 |
| DOC-007 | 5 | 71,17 → 71,56 | 7 → 5 | 13 → 9 | 93 → 95 | 82,2 % → 83,5 % | `REVIEW_REQUIRED` | 0/178 |
| DOC-008 | 2 | 68,67 → 68,67 | 4 → 4 | 8 → 8 | 23 → 23 | 68,2 % → 68,2 % | `REVIEW_REQUIRED` | 0/74 |
| **Corpus** | 31 | **65,7063 → 64,4737** | 42 → 53 | 80 → 105 | 500 → 490 | — | 8/8 `REVIEW_REQUIRED` | 0/1072 |

Les PDF produits, aperçus, planches comparatives et agrandissements existent pour les 8 documents (31 pages) dans l'espace privé du RUN29 ; ils ne sont **pas** versionnés (confidentialité). Ce dossier n'en publie que des compteurs anonymisés.

## Ce que le RUN29 a réellement corrigé

Chaque correction est prouvée par un test qui échoue sans elle (contre-épreuve), par le rejeu des 8 documents et par l'inspection visuelle des PDF produits.

| Défaut (vérifié à l'œil) | Documents | RUN28 → RUN29 | Correctif |
|---|---|---|---|
| Bord de case à cocher recouvert par un masque | DOC-004 | 3 → 0 ; `PROTECTED_REGION_CHANGED` 6 → 0 | F43 : dégagement sûr autour des zones protégées |
| Moitiés de mots, chiffres, lettres de tampon ou logo coupés par une couverture | DOC-001, 004, 005, 006 | 12 → 0 | F50, F50b, F50c : placement refusé, original conservé, anomalie critique |
| Valeur manuscrite remplacée par une phrase inventée | DOC-002 | 1 → 0 | F51 : un seul mot court reconnu à très basse confiance n'est plus une preuve |
| Tampon et logo partiellement effacés et « traduits » | DOC-006 | 2 → 0 | F50c |
| Traduction barrée par un filet de tableau conservé | DOC-004 | 2 cas → 0 | F53 : placement refusé, filet et original conservés |
| Filet de tableau effacé sous une couverture | DOC-004, DOC-006 | 10 → 5, les 5 restants **signalés critiques** | F48, F48b (préservation) ; F49 (nouveau contrôle `RENDER_RULE_ERASED`) |
| Lignes non traduites car trop longues | DOC-004, 006, 007 | 14 → 8 débordements | F44 (deux lignes réduites), F45 (interligne serré) ; lisibilité à valider |
| Garde de budget 32 768 du moteur privé inopérante avec `transformers` 5 | moteur privé | fail-open → fail-closed | F46, F47 |
| Requêtes de plusieurs centaines de blocs envoyées au moteur privé, rejetées en bloc | moteur privé | gpt-oss, 8 documents : 5 → 420 blocs traduits (DOC-004 : 0 → 90) | F52 : plafond de 40 blocs et redécoupage borné, comme Interim |

## Pourquoi le score baisse

La baisse (−1,2326) **n'est pas** un changement de formule : les deux règles de mesure, RUN28 et RUN29, donnent des valeurs identiques sur les mêmes fichiers. Elle a deux causes, détaillées dans [RUN29-BEFORE-AFTER.md](RUN29-BEFORE-AFTER.md) :

1. **14 traductions** que le RUN28 plaçait sur un rendu endommagé (glyphes coupés, texte barré) sont désormais refusées. L'original reste intact, mais la méthode gelée compte la traduction manquante. DOC-005 perd ainsi son seul bloc traduit.
2. Des défauts **préexistants**, invisibles aux métriques RUN28, sont désormais mesurés : 12 couvertures coupant des glyphes, 5 filets effacés, 2 textes barrés.

Défauts critiques scorecard-2 : 42 → 53. Alertes produit critiques : 80 → 105. Ce sont des défauts **rendus visibles**, pas des défauts nouveaux introduits par le RUN29 : les 24 changements de statut sont tous attribués à un correctif.

## Ce qui reste ouvert (extrait)

| Défaut | Gravité | Documents |
|---|---|---|
| 8 lignes encore en débordement (cellules de 5 à 7 pt) | critique | DOC-004, DOC-007, DOC-008 |
| Arabe et hébreu non façonnés au rendu (3 refus) ; phrases RTL scindées par l'OCR et traduites ligne à ligne | critique | DOC-001, DOC-004, DOC-006 |
| Trait de signature lu comme deux lettres et reporté dans la traduction (préexistant) | critique | DOC-004 |
| 5 filets encore effacés (signalés) | critique | DOC-004, DOC-006 |
| 14 traductions refusées par prudence : il faut étendre la couverture à l'emprise réelle des glyphes | majeur | DOC-001, 004, 005, 006 |
| Lisibilité des lignes réduites, condensées ou à interligne serré | majeur | DOC-004, 006, 007 |
| 83 blocs que Interim a renvoyés sans traduction, 152 blocs `UNCERTAIN` | majeur | 7/8 et 8/8 |

Liste complète, limites de mesure et prérequis manquants : [RUN29-OPEN-ISSUES.md](RUN29-OPEN-ISSUES.md).

## Moteurs de traduction

gpt-oss-20b (poids officiels publiés par OpenAI, `llama.cpp` local lié à `127.0.0.1`, CPU) a été branché sur la chaîne dans les mêmes conditions que Interim : même code, même IR, mêmes gardes, même budget 32K, aucun repli public.

- **Première passe : 5 blocs traduits seulement.** Cause dans le code, pas seulement dans le modèle : le mode moteur privé envoyait des requêtes de 121 à 334 blocs sans redécoupage, et une seule réponse invalide faisait rejeter tout le lot. Corrigé par **F52** (40 blocs au plus, redécoupage borné). **F46/F47** ont corrigé deux défauts du contrôle 32K du moteur privé, dont un fail-open (la garde de budget ne bloquait rien avec `transformers` 5).
- **Passe finale sur les 8 originaux (avec F52)** : 8/8 exécutés, 77 requêtes, **0 violation de budget**, 0 réponse finalement rejetée, originaux inchangés. Mais **420 blocs traduits et placés contre 492** avec Interim, **150 sources renvoyées inchangées contre 83**, **6 défauts critiques d'entités contre 0**, environ 110 s par requête sur 1 vCPU.
- **Réponse à « ça marchera mieux ? » : non démontré, indices défavorables.** gpt-oss-20b n'est pas qualifié et ne remplace pas Interim ; qualité de traduction non mesurée (0 référence humaine). Détails : [RUN29-ENGINE-COMPARISON.md](RUN29-ENGINE-COMPARISON.md).

## Validation humaine

**0 ligne revue sur 1 072.** Le pack de revue privé est prêt pour les 8 documents (`NOT_STARTED`). Aucune ligne n'est promue automatiquement. Sans revue, le sens n'est pas mesurable et le seuil de 94 reste inaccessible.

## Tests

873 tests backend passés (0 échec, 0 ignoré), dont 71 nouveaux tests RUN29 ; golden 8/8 passés (pipeline technique sur les 8 originaux, moteur `offline`, aucun modèle invoqué) ; frontend non modifié : typecheck, 30 tests et build passés ; `ruff`, `pip-audit --strict` et `npm audit` sans anomalie. Moteurs et transports factices identifiés comme tels ; aucune inférence complète n'est prouvée par un test automatisé. Détail : [RUN29-TESTS.md](RUN29-TESTS.md).
