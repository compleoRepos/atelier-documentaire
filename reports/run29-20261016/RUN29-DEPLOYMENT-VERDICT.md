# RUN29 — Verdict de mise en service

## Verdict : **NO-GO**

> Le moteur de traduction documentaire **ne peut pas être mis en service** pour un usage bancaire ou client à l'issue du RUN29. Les 8 documents restent `REVIEW_REQUIRED` ; 7 sur 8 portent au moins un défaut critique mesuré ; aucune ligne de référence humaine n'a été revue (0/1 072) ; aucun moteur privé de production n'est qualifié ; le score officiel du corpus (borne basse v2) vaut **64,4737**, loin du seuil de 94, qui est d'ailleurs inaccessible sans références humaines (plafond 75,4630).

Le classement « GO sous réserve » est écarté : il supposerait des défauts résiduels tous non critiques et une validation humaine au moins partielle, deux conditions non remplies.

## 1. Critères d'acceptation de la mission

| Critère | État | Preuve |
|---|---|---|
| Aucun défaut critique connu dissimulé | **rempli** | 53 défauts critiques scorecard-2 et 105 alertes produit critiques publiés ; défauts vus seulement à l'œil listés (`MV-xx`) ; aucun seuil modifié |
| Entités critiques préservées ou transformations justifiées | **non démontré** | les gardes d'entités n'acceptent aucune altération mesurée, mais la mesure compare à l'OCR, pas à l'image ; un trait de signature lu comme du texte (MV-18) et des phrases RTL scindées (MV-06) restent ouverts sur DOC-004 |
| Omissions corrigées ou explicitement signalées | **signalées, non corrigées** | 116 blocs `FAILED` et 152 `UNCERTAIN`, tous explicites ; 14 refus prudents nouveaux (OI-07) |
| Défauts de mise en page corrigés ou documentés | **documentés** | 8 débordements, 5 filets effacés, lisibilité des lignes réduites à valider ([RUN29-OPEN-ISSUES.md](RUN29-OPEN-ISSUES.md)) |
| Résultats reproductibles | **rempli** | baseline RUN28 reproduite au pixel près (31/31 pages) ; mêmes valeurs sous les deux règles de mesure ; empreintes de code identiques au début et à la fin de chaque exécution |
| Régressions identifiées | **rempli** | 24 transitions de statut attribuées à un correctif ; baisse du score expliquée document par document ([RUN29-BEFORE-AFTER.md](RUN29-BEFORE-AFTER.md)) |
| Qualité linguistique et qualité visuelle évaluées séparément | **partiel** | visuel : inspection des fichiers produits ; linguistique : **non évaluée** (0 référence humaine, sens non mesurable) |
| Aucun document conforme avec une donnée essentielle altérée | **rempli** | aucun document n'est déclaré conforme |
| Validation finale sur les fichiers réellement générés | **rempli pour le visuel** | planches et agrandissements des PDF produits (privés) |

## 2. Verdict par document

| Document | Défauts critiques sc-2 | Alertes produit critiques | Défauts critiques vus à l'œil encore ouverts | v2 borne basse [haute] | Plafond sans humain | Lignes humaines revues | Verdict |
|---|---|---|---|---|---|---|---|
| DOC-001 | 4 | 8 | 0 | 60,0 [83,2] | 76,9 | 0/47 | **NO-GO** |
| DOC-002 | 4 | 8 | 0 | 66,4 [89,6] | 76,9 | 0/24 | **NO-GO** |
| DOC-003 | 0 | 0 | 0 | 62,7 [94,2] | 68,5 | 0/13 | **NO-GO** |
| DOC-004 | 21 | 42 | 3 | 65,7 [88,9] | 76,9 | 0/229 | **NO-GO** |
| DOC-005 | 4 | 8 | 0 | 47,1 [73,2] | 74,1 | 0/89 | **NO-GO** |
| DOC-006 | 11 | 22 | 3 | 73,5 [96,7] | 76,9 | 0/418 | **NO-GO** |
| DOC-007 | 5 | 9 | 0 | 71,5 [94,8] | 76,9 | 0/178 | **NO-GO** |
| DOC-008 | 4 | 8 | 0 | 68,6 [91,9] | 76,9 | 0/74 | **NO-GO** |

La colonne « vus à l'œil » compte les occurrences recomptées en RUN29 : filets encore effacés (MV-10 : DOC-004 2, DOC-006 3) et trait de signature (MV-18 : DOC-004 1). Les phrases RTL scindées de DOC-004 (MV-06, 5 lignes en RUN28) **ne sont pas recomptées** et n'y figurent donc pas : elles restent ouvertes.

Une borne haute supérieure à 94 (DOC-003, DOC-006, DOC-007) suppose que **toutes** les inconnues seraient parfaites : elle ne vaut pas validation. DOC-003 n'a aucun défaut critique mesuré mais seulement 2 blocs traduits et aucune relecture : il reste non validé.

## 3. Motifs bloquants

| Motif | Gravité | Détail |
|---|---|---|
| Défauts critiques sur 7 documents | bloquant | 53 défauts scorecard-2 ; aucun score moyen ne compense un défaut critique |
| Validation humaine absente | bloquant | 0/1 072 ligne revue ; le mécanisme de revue existe (pack privé prêt, `NOT_STARTED` × 8) |
| Moteur privé non qualifié | bloquant | Interim est un fournisseur **temporaire** autorisé pour ces 8 originaux uniquement ; gpt-oss-20b local n'est pas qualifié ([RUN29-ENGINE-COMPARISON.md](RUN29-ENGINE-COMPARISON.md)) ; Qwen/vLLM indisponibles |
| Écritures de droite à gauche | bloquant pour les documents arabes/hébreux | façonnage absent (3 refus explicites) et phrases scindées (MV-06) |
| Détecteurs non validés hors corpus | majeur | rappel de F49, F50 et F53 non mesuré |

## 4. Ce que le RUN29 permet de garantir

- Une anomalie critique **bloque** la validation automatique : aucun document n'est promu, le statut reste `REVIEW_REQUIRED`.
- Un rendu qui couperait des glyphes de l'original, effacerait un filet sans le signaler ou barrerait une traduction est refusé ou signalé critique, avec l'original conservé.
- Le moteur privé échoue **fermé** si le contrôle préalable du budget 32 768 ne peut pas s'exécuter (F46, F47).
- Les originaux ne sont jamais modifiés (empreintes vérifiées).

## 5. Conditions de levée du NO-GO

| # | Condition | Mesure de réussite |
|---|---|---|
| 1 | Revue humaine des 8 documents par des réviseurs qualifiés, via le mécanisme existant | 1 072/1 072 lignes revues, corrections enregistrées, aucune ligne promue automatiquement |
| 2 | Zéro défaut critique non accepté par le métier | chaque défaut critique résiduel corrigé ou accepté formellement, document par document |
| 3 | Moteur privé qualifié sur le même corpus et dans les mêmes conditions (code, IR, budgets) | taux de traduction et taux d'échec comparables ou meilleurs que Interim, 0 violation de budget, revue humaine d'un échantillon |
| 4 | Façonnage RTL et regroupement des phrases avant traduction | 0 refus `RTL_SHAPING_UNSUPPORTED`, MV-06 corrigé et vérifié à l'œil |
| 5 | Signatures traitées comme zones protégées | MV-18 corrigé et vérifié |
| 6 | Jeu de validation indépendant pour F49, F50 et F53 | précision et rappel mesurés hors corpus de calibration |
| 7 | Score officiel recalculé avec les références humaines | borne basse v2 ≥ 94 selon la méthode gelée, sans modification de formule |

## 6. Usage possible en attendant

Aucun usage client ou bancaire. Un usage **interne d'aide à la traduction** reste envisageable uniquement si chaque document produit est traité comme un **brouillon** relu intégralement par un humain qualifié, et si ses alertes sont lues avant toute diffusion. Ce n'est pas une mise en service.
