# RUN18 — Rapport de régression (baseline / run17 / run18)

Verdict run18 = passage `run24`, code d'empreinte `4d4956273c97d866` (empreinte SHA-256 des sources
`backend/app` et `tools`, identique au début et à la fin de la suite de tests). Les trois runs sont mesurés
par **le même outil et la même méthode** (`tools/recette/measure_v2.py`, méthode `measure-v2.1-run18`) sur
les sorties privées ; seuls des compteurs anonymisés sont versionnés
(`metrics/RUN18_METRICS_BY_DOCUMENT.json`). Les 8 documents restent **`REVIEW_REQUIRED`** : aucun PASS
artificiel.

Traductions : moteur **temporaire Interim** (`served_model` gpt-5-mini). Ce ne sont **pas** des résultats de
validation de Qwen. Le verdict réutilise par mémoire de traduction (F16) les cibles obtenues aux passages
run19, run21 et run22 ; aucune requête au passage final. Chaîne complète : 61 requêtes, réservation maximale
22 467 tokens ≤ 32 768, **0 violation de budget** (détail : rapport de couverture §6).

## 1. Définitions (identiques pour les trois runs)

| Terme | Définition |
|---|---|
| Attendu | caractères des blocs source qui doivent être traduits ; décidé sur le texte source seul (langue recalculée par la même fonction pour tous les runs ; français, noms, identifiants, contenus sans mot exclus) |
| Écrit | caractères attendus dont les mots de la cible sont retrouvés dans le PDF rendu, près du bloc (rappel ≥ 0,85) |
| Partiel / Absent | rappel entre 0,25 et 0,85 / traduction tentée mais rappel < 0,25 |
| Couverture écrite | écrit / attendu |

L'attendu varie légèrement d'un run à l'autre parce que la **segmentation** diffère (un bloc scindé ou
fusionné change l'ensemble des blocs) ; la règle de décision, elle, est la même.

## 2. Synthèse

| Document | Couverture écrite baseline | run17 | run18 | Δ run18 − run17 | Δ run18 − baseline |
|---|---|---|---|---|---|
| DOC-001 | 0,598 | 0,555 | 0,576 | +0,021 | −0,022 |
| DOC-002 | 0,434 | 0,273 | 0,393 | +0,120 | −0,041 |
| DOC-003 | 0,000 | 0,741 | 0,741 | 0,000 | +0,741 |
| DOC-004 | 0,717 | 0,361 | 0,538 | **+0,177** | −0,179 |
| DOC-005 | 0,044 | 0,155 | 0,454 | **+0,298** | +0,409 |
| DOC-006 | 0,913 | 0,953 | 0,937 | −0,016 | +0,024 |
| DOC-007 | 0,796 | 0,710 | 0,763 | **+0,053** | −0,034 |
| DOC-008 | 0,547 | 0,646 | 0,640 | −0,006 | +0,093 |
| **Total** | **0,8365** (36 039 / 43 085) | **0,8195** (34 955 / 42 652) | **0,8364** (35 939 / 42 967) | **+0,0169** | **−0,0001** |

Lecture :

* run18 **efface la régression globale de run17** et revient au niveau de la baseline (écart −0,0001), avec
  en plus des contrôles plus stricts que la baseline (la baseline réduisait ou tronquait sans signaler,
  rapport de causes §2).
* Les priorités 1 (DOC-004, DOC-005, DOC-007) et 2 (DOC-001, DOC-002) progressent toutes par rapport à
  run17. DOC-004, DOC-007, DOC-001 et DOC-002 **restent sous la baseline** : limitation documentée (§3),
  pas une acceptation.
* DOC-006 et DOC-008 reculent légèrement par rapport à run17 tout en restant au-dessus de la baseline :
  analysé au §4, non masqué.
* DOC-003 : la baseline n'écrivait rien (0 / 36) ; run17 et run18 sont identiques.

## 3. Documents prioritaires

### DOC-004 (priorité 1) — 0,361 → 0,538 (baseline 0,717)

| Indicateur (baseline / run17 / run18) | Valeur |
|---|---|
| Caractères écrits | 2 610 / 1 250 / 1 849 |
| Blocs TRANSLATED (run17 → run18) | 54 → 82 ; FAILED 68 → 46 |
| `LAYOUT_OVERFLOW` | 4 / 17 / 13 |
| Caractères absents par débordement | 176 / 664 / 455 |
| Caractères absents par encre résiduelle (D20) | 0 / 272 / 345 |
| Mots insérés en collision | 0 / 5 / 0 |
| Régions visuelles altérées | 7 / 10 / **1** |

Causes traitées : C1 (F1), C2 (F2, F2b), C3 (F5, F12), C4 (F3), cases (F9, F13, F13b, F15, F17, F18).
Preuve visuelle (zooms privés) : cases d'option préservées, plus de coupure intra-mot, libellés alignés à
droite écrits dans l'espace libre de la cellule.

Reste sous la baseline. Causes résiduelles mesurées : débordements (le français est environ deux fois plus
long que les libellés arabes dans des cellules étroites ; la baseline réduisait/tronquait sans le signaler,
run18 refuse et signale), encre résiduelle sous des masques rétrécis (garde D20), 264 caractères renvoyés
inchangés par Interim malgré la reprise, 154 caractères `ocr_unreliable` volontairement non envoyés (F13b,
F18). `PROTECTED_REGION_CHANGED` ×8 est **nouveau** : les cases sont désormais déclarées comme régions
protégées et contrôlées ; l'alerte est légitime (faible différence de pixels près des masques) et conservée.

### DOC-005 (priorité 1) — 0,155 → 0,454 (baseline 0,044)

Document majoritairement français : 1 657 caractères `already_french` hors périmètre. La « chute » de run17
était un artefact de dénominateur (rapport de causes §2). Avec F4, l'attendu ne contient plus que les blocs
réellement étrangers (366 caractères). Reste : 93 caractères renvoyés inchangés par Interim, 88 caractères
écartés par la garde d'encre résiduelle (`SCAN_TEXT_OVER_SOURCE_INK` ×1), 14 caractères de structure de
formulaire ambiguë.

### DOC-007 (priorité 1) — 0,710 → 0,763 (baseline 0,796)

| Indicateur (baseline / run17 / run18) | Valeur |
|---|---|
| Caractères écrits | 7 333 / 6 316 / 6 844 |
| Absents par encre résiduelle | 0 / 1 146 / 732 |
| Absents par débordement | 263 / 408 / 354 |
| `SCAN_TEXT_OVER_SOURCE_INK` | 0 / 16 / 8 |
| `LAYOUT_OVERFLOW` | 2 / 11 / 9 |
| Mots insérés en collision | 0 / 29 / **0** |

F1 a supprimé l'essentiel de la cause C1 (−414 caractères bloqués par l'encre). F19 supprime les lignes
superposées présentes depuis run17 : la traduction qui montait sur la ligne voisine est désormais refusée
et signalée (débordement), ce qui coûte 100 caractères écrits par rapport au passage précédent mais rend le
défaut **visible** au lieu d'illisible. Reste sous la baseline : encre résiduelle (732), 537 caractères
renvoyés inchangés par Interim, 159 caractères rejetés par la garde d'entités. `UNMAPPED_TABLE_CONTENT` ×1
conservé (cadres pleine page de deux versos blancs, aucun texte perdu ; rapport de causes §5).

### DOC-001 (priorité 2) — 0,555 → 0,576 (baseline 0,598)

Aucun bloc écrit en run17 n'est perdu. Restent : 140 caractères `form_structure_ambiguous` (garde D16),
93 caractères dont la cible contient de l'arabe (façonnage RTL non supporté, F6 non implémenté,
fail-closed), 24 caractères renvoyés inchangés.

### DOC-002 (priorité 2) — 0,273 → 0,393 (baseline 0,434)

Le blocage par encre résiduelle de run17 (91 caractères) a disparu ; `LAYOUT_OVERFLOW` 1 → 0. Restent :
206 caractères rejetés par la garde d'entités (comportement voulu : la sortie modifiait une entité protégée),
159 renvoyés inchangés par Interim, 133 caractères dont le masque serait dangereux (`render_mask_unsafe`).

## 4. Non-régression DOC-006 et DOC-008, attribution code / moteur

La variance de Interim (70,6 % des caractères avec une cible différente à source identique entre deux
passages) empêche d'attribuer naïvement une différence run17 → run18 au code. Une **expérience contrôlée
privée** a donc été exécutée : code run18 (empreinte du passage run21, avant F17–F19) avec, pour chaque bloc
de même identifiant et de même source, **la cible de run17** ; 0 requête.

| Document | run17 | Expérience (code run18 + cibles run17) | run18 (verdict) | Lecture |
|---|---|---|---|---|
| DOC-006 | 0,953 | 0,940 | 0,937 | −0,013 lié au code : la nouvelle segmentation crée des blocs dont la source diffère, ils n'ont pas de cible run17 et ont été traduits au passage run19, où Interim a renvoyé la source pour une partie d'entre eux (caractères « renvoyés inchangés » 517 → 970) ; −0,003 de variance moteur |
| DOC-008 | 0,646 | 0,640 | 0,640 | −8 caractères ; le reste est égal à run17 |
| Total | 0,8195 | 0,8445 | 0,8364 | le code run18 seul apporte +0,025 sur les cibles run17 |

DOC-006 perd 16 blocs écrits par rapport à run17 (environ 613 caractères) : 12 blocs restés en source après
un retour inchangé de Interim et une reprise (≈ 506 caractères), le reste en défauts signalés (débordement,
croissance refusée, source différente). Deux alertes critiques **nouvelles** apparaissent : une date collée
par l'OCR (« mois+année » sans espace) est classée comme code ; run17 l'avait laissée en anglais, la cible
run18 traduit le mois. La valeur reste exacte ; la garde conservatrice signale l'écart
(`CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1) et elle est conservée.

DOC-008 : un bloc partiel de run17 n'est plus écrit (débordement signalé au lieu d'un rendu partiel) ;
l'encre résiduelle (85 → 0) et `SCAN_TEXT_OVER_SOURCE_INK` (1 → 0) disparaissent.

## 5. Critères du prompt §13

| # | Critère | Résultat | Preuve |
|---|---|---|---|
| 1 | Les trois documents les plus dégradés corrigés ou limitations documentées | DOC-004 +0,177, DOC-005 +0,298, DOC-007 +0,053 vs run17 ; DOC-004 et DOC-007 restent sous la baseline, causes résiduelles chiffrées §3 et `LIMITATIONS.md` | ce rapport, rapport de causes |
| 2 | La couverture écrite ne régresse pas silencieusement | total 0,8195 → 0,8364 (baseline 0,8365) ; reculs DOC-006 −0,016 et DOC-008 −0,006 expliqués §4 | métriques JSON |
| 3 | Débordements et textes coupés mesurés avec la même méthode | même outil v2.1 pour les trois runs ; codes et mesure dans le PDF rendu | rapport de fidélité §2 |
| 4 | Régions graphiques altérées identifiées et examinées | 2 154 régions candidates, altérées par run et par type, planches et audits privés examinés | rapport de fidélité §3 |
| 5 | Données critiques exactes | aucune valeur critique altérée constatée : les 3 blocs `PROTECTED_ENTITY_CHANGED` gardent la source ; la date et les longueurs signalées dans DOC-006 sont exactes (alertes conservées) | rapport de fidélité §4 |
| 6 | Tableaux et champs conservent leurs relations | scissions F2/F10/F13 avec remappage des références de tableaux ; `UNMAPPED_TABLE_CONTENT` DOC-007 conservé | rapport de fidélité §5 |
| 7 | Les améliorations ne dégradent pas les autres documents | DOC-003 identique ; DOC-006/DOC-008 légers reculs expliqués ; F17/F18/F19 sans effet hors de leur cible | §4, rapport de causes §4 |
| 8 | Les tests existants continuent de passer | 591 passed, 0 failed (verdict et état final committé) ; golden local 8 passed (technique) ; Angular typecheck, 16 tests, build | `TEST_RESULTS.md` |
| 9 | Les défauts non résolus restent visibles | 8 documents `REVIEW_REQUIRED`, statut et raison par bloc, codes critiques listés | rapport de couverture §4, `LIMITATIONS.md` |
| 10 | Résultats reproductibles | empreinte de code, lanceur versionné, mémoire de traduction à signature, mesure versionnée ; Interim non déterministe sans mémoire (§4) | rapport de causes §6–§7 |

Conclusion : run18 est **livrable en `REVIEW_REQUIRED`**. Il corrige les causes racines identifiées de
run17, récupère la couverture globale de la baseline avec des contrôles plus stricts, et laisse visibles
les limites restantes. Il ne prétend pas à un PASS documentaire : aucune référence humaine n'existe pour
ces documents et des alertes critiques réelles subsistent.
