# RUN25 — Rapport de régression

Comparaison, avec une seule méthode de mesure, de la baseline, de run17, du dernier run réellement disponible
(run24) et du run final run25 (prompt run25 §15, §16 et §19). Aucun texte de document, nom de fichier, empreinte de
document ni chemin privé ne figure ici. Les chiffres proviennent de `metrics/RUN25_METRICS_BY_DOCUMENT.json`
(export anonymisé) et de `metrics/RUN25_LIVE_GENERATION_CHECK.json`.

## 1. Runs comparés et provenance des traductions

| Libellé | Contenu | Code | Traductions |
|---|---|---|---|
| baseline | sorties du 08/10, figées | code du 08/10 | génération Interim du 08/10 |
| run17 | référence précédente, figée | code run17 | génération Interim run17 |
| run24 | dernier run disponible (« verdict run18 »), figé | `026b0f9`, empreinte `4d4956273c97d866` | mémoire de run19 et générations ultérieures |
| **run25** (final, run25e) | 8 documents rejoués | `026b0f9` + corrections F20–F24, empreinte `f4a84aaef38c7c7d` | **mémoire de traduction de run24** : 0 requête au moteur IA |
| run25-live (supplémentaire) | 8 documents rejoués | même code `f4a84aaef38c7c7d`, même analyse | **nouvelle génération Interim** : 63 requêtes |

Conséquences pour la lecture des écarts :

* **run24 → run25** : traductions identiques à source identique, donc l'écart est attribuable au **seul code**.
* **baseline ou run17 → run25** : le code **et** la génération diffèrent. La génération Interim varie fortement d'un
  passage à l'autre (§6) ; ces écarts ne sont donc pas attribuables au code seul.
* Le run supplémentaire run25-live mesure ce que donne une génération réelle avec le code final. Il n'est **pas** le
  verdict, et Interim n'est pas une validation de Qwen.

Méthode : `measure-v2.1-run18` (outil versionné `tools/recette/measure_v2.py` et `tools/recette/render_outcome.py`)
appliquée de la même façon aux cinq jeux. Le périmètre attendu est recalculé avec une seule règle de langue pour
tous les runs, et le rendu est mesuré dans le PDF produit par extraction indépendante. Le registre d'anomalies
(`tools/recette/anomaly_register.py`) applique les mêmes règles.

## 2. Synthèse globale

| Indicateur (8 documents) | baseline | run17 | run24 | run25 |
|---|---|---|---|---|
| Caractères attendus (périmètre) | 43 085 | 42 652 | 42 967 | 42 967 |
| Couverture écrite | 0,8365 | 0,8195 | 0,8364 | **0,8419** |
| Caractères écrits | 36 039 | 34 955 | 35 939 | **36 173** |
| Caractères partiels | 216 | 292 | 226 | 226 |
| Caractères absents (tentés mais introuvables dans le PDF) | 2 342 | 3 341 | 2 842 | **2 374** |
| Mots insérés en collision | — | 34 | 0 | **0** |
| Codes critiques (somme des occurrences) | 55 | 112 | 115 | **105** |
| dont `SCAN_TEXT_OVER_SOURCE_INK` | 0 | 25 | 19 | **9** |
| dont `LAYOUT_OVERFLOW` | 6 | 35 | 29 | 29 |
| dont `PROTECTED_REGION_CHANGED` (cases DOC-004) | 0 | 0 | 8 | 8 |
| dont `UNMAPPED_TABLE_CONTENT` (DOC-007) | 1 | 1 | 1 | 1 |
| Régions graphiques altérées (> 2 % des pixels) | 63 | 89 | 83 | **81** |
| Encre originale effacée hors des blocs écrits (px) | — | — | 13 117 | **6 573** |
| Statut des 8 documents | — | — | `REVIEW_REQUIRED` | `REVIEW_REQUIRED` |

La baseline a moins de codes critiques que run17, run24 et run25. Ce n'est pas un signe de meilleure fidélité :
plusieurs contrôles (`SCAN_TEXT_OVER_SOURCE_INK`, `PROTECTED_REGION_CHANGED`, contrôle de troncature) n'existaient
pas encore le 08/10, et ses troncatures n'étaient pas signalées (constat run18).

## 3. Couverture écrite par document

| Document | baseline | run17 | run24 | run25 | Δ run25 − run24 | Δ run25 − baseline |
|---|---|---|---|---|---|---|
| DOC-001 | 0,598 | 0,555 | 0,576 | 0,576 | +0,000 | −0,022 |
| DOC-002 | 0,434 | 0,273 | 0,393 | 0,393 | +0,000 | −0,041 |
| DOC-003 | 0,000 (non comparable) | 0,741 | 0,741 | 0,741 | +0,000 | — |
| DOC-004 | 0,717 | 0,361 | 0,538 | **0,589** | **+0,051** | −0,128 |
| DOC-005 | 0,044 | 0,155 | 0,454 | 0,454 | +0,000 | +0,409 |
| DOC-006 | 0,913 | 0,953 | 0,937 | 0,937 | +0,000 | +0,024 |
| DOC-007 | 0,796 | 0,710 | 0,763 | **0,778** | **+0,015** | −0,019 |
| DOC-008 | 0,547 | 0,646 | 0,640 | **0,591** | **−0,049** | +0,044 |
| **Total** | 0,8365 | 0,8195 | 0,8364 | **0,8419** | +0,0055 | +0,0054 |

La couverture tentée (« couverture stricte » au sens historique) figure dans
`RUN25_TRANSLATION_COVERAGE_REPORT.md`.

## 4. Analyse par document

### DOC-004 (priorité absolue)

| Indicateur | run24 | run25 |
|---|---|---|
| Couverture écrite | 0,538 | 0,589 |
| Blocs TRANSLATED / FAILED / UNCERTAIN | 82 / 46 / 45 | 86 / 41 / 46 |
| Caractères absents | 1 014 | 804 |
| `SCAN_TEXT_OVER_SOURCE_INK` | 8 | 3 |
| `LAYOUT_OVERFLOW` | 13 | 14 |
| Registre : cible manquante / source résiduelle | 29 / 51 | 24 / 52 |
| Régions de cases altérées (27 cases) | 0 | 0 |
| Encre effacée hors blocs écrits | 4 383 px | 1 743 px |

* **Gains attribuables au code** : F20 et F20b (5 blocs récupérés), F24 (bordures de rangées restaurées), F23 (un
  numéro dont les groupes étaient inversés n'est plus rendu ; l'original est conservé).
* Le `LAYOUT_OVERFLOW` supplémentaire porte sur `p001-b0077`, déjà refusé en run24 pour masque dangereux
  (`render_mask_unsafe`) et refusé en run25 pour débordement. La source est conservée dans les deux cas : le motif
  de refus change, pas le résultat.
* Les 27 cases restent intactes (0 % de pixels modifiés en run24 et run25 ; jusqu'à 98 % en run17 et 74 % dans la
  baseline). Les 8 alertes moteur `PROTECTED_REGION_CHANGED` sur ces cases sont **maintenues** : elles relèvent d'un
  seuil plus strict que la mesure indépendante, et elles n'ont pas été levées.
* Écart persistant à la baseline (−0,128) : le code et la génération diffèrent tous deux. Les refus actuels
  (débordements en cellule, OCR non fiable, sources rendues par le moteur IA) sont des refus sûrs qui conservent
  l'original. Ils sont décrits dans `LIMITATIONS.md`.

### DOC-007 (priorité absolue)

| Indicateur | run17 | run24 | run25 |
|---|---|---|---|
| Couverture écrite | 0,710 | 0,763 | 0,778 |
| Blocs TRANSLATED / FAILED | — | 87 / 48 | 93 / 41 |
| Caractères absents | — | 1 118 | 867 |
| Mots en collision | 29 | 0 | 0 |
| `SCAN_TEXT_OVER_SOURCE_INK` | — | 8 | 3 |
| `LAYOUT_OVERFLOW` | — | 9 | 8 |
| Registre : cible manquante / texte sur encre | — | 18 / 1 | 12 / 0 |

* **Gains attribuables au code** : F20 et F20b (7 blocs récupérés), dont le titre `p001-b0038`, passé du refus
  pour débordement à « traduit et placé ».
* **Régressions détectées puis corrigées pendant run25** :
  * filet de cadre effacé sous ce titre (run25a), corrigé par F22 puis F22b. La part sombre du filet est de 1,00
    sur l'original, 0,03 en run25a et 1,00 en run25 final ;
  * cases vides d'une ligne d'options exposées par F20, protégées par F21.
* F21 réduit de 114 le nombre de caractères tentés (8 044 → 7 930) : la ligne d'options passe en `UNCERTAIN` et
  conserve ses cases.
* L'alerte réelle `UNMAPPED_TABLE_CONTENT` (1) est conservée.
* Chaque débordement restant a été classé par cause : 7 sur 8 proviennent d'une source qui ne tient pas elle-même
  dans sa boîte à la police de rendu, plus large que la police condensée du scan (voir `RUN25_ROOT_CAUSE_ANALYSIS.md`
  §4).

### DOC-008 (priorité absolue)

| Indicateur | run17 | run24 | run25 |
|---|---|---|---|
| Couverture écrite | 0,646 | 0,640 | 0,591 |
| Blocs TRANSLATED / UNCERTAIN | — | 23 / 1 | 22 / 2 |
| Français déjà présent réécrit (car.) | — | 0 | 0 |
| Régions monochromes (cachet, signature, certification) altérées | 0 sur 8 | 0 sur 8 | 0 sur 8 |
| Régions altérées (bandes d'image pleine largeur) | 50 | 48 | 46 |
| Encre effacée hors blocs écrits | — | 2 231 px | 809 px |

* **Baisse volontaire de −0,049** : F23 retire du rendu la ligne de coordonnées du pied de page, dont les numéros
  étaient rendus avec leurs groupes de chiffres inversés (donnée critique fausse depuis run24 au moins). Ces 85
  caractères étaient « écrits » mais faux. Le bloc passe en `UNCERTAIN` et l'original reste visible.
* La traduction française certifiée n'est pas retraduite : 23 blocs déjà en français (980 caractères) sont conservés
  et aucun caractère français n'est réécrit.
* Les 46 régions altérées sont toutes chevauchées par un bloc traduit et écrit. Elles sont localisées (page et
  coordonnées) dans l'export JSON (`altered_regions_run25`). Aucune ne touche le cachet, la signature ou les
  éléments de certification.

### DOC-005 (priorité suivante)

* Couverture écrite inchangée depuis run24 (0,454), contre 0,044 dans la baseline et 0,155 en run17. Couverture
  tentée : 0,694.
* Le contenu non traduit est classé : 48 blocs déjà en français (1 678 caractères), 27 identifiants ou données à
  préserver, 2 illisibles, 9 en revue humaine (195 caractères), 0 réellement oublié.
* F24 restaure le premier glyphe d'une ligne française conservée, qui était effacé par le masque voisin. L'encre
  effacée hors blocs écrits passe de 165 à 87 px.
* Reste 1 refus « encre résiduelle » (88 caractères), décision sûre conservée.

### DOC-006 (non-régression)

* Couverture écrite 0,937 identique à run24. TRANSLATED 266 → 267, cible manquante 10 → 9,
  `SCAN_TEXT_OVER_SOURCE_INK` 2 → 1.
* 16 pages sur 16 conservées. Alertes d'entités critiques identiques à run24 (97 lignes au registre).
* Encre effacée hors blocs écrits : 5 460 → 3 330 px (soulignements de titres et filets de formulaire).
* Écart à run17 (−0,016) : expliqué en run18, essentiellement des retours inchangés du moteur IA.
* **Aucune régression run24 → run25.**

### DOC-001, DOC-002, DOC-003

* DOC-001 (0,576) et DOC-003 (0,741) : identiques à run24.
* DOC-002 (0,393) : couverture identique à run24. Le bloc `p001-b0003` change de motif de refus :
  `NATIVE_REDACTION_OVERLAP` (erreur) en run24, `SCAN_TEXT_OVER_SOURCE_INK` (critique) en run25. Le résultat est le
  même : la source est conservée. Cela explique l'unique occurrence nouvelle de ce code.
* La valeur 0 de la baseline en DOC-003 n'est pas comparable : la baseline réécrivait du français hors périmètre.

## 5. Régressions rencontrées pendant run25 et leur traitement

| Régression | Introduite par | Détection | Traitement | État final |
|---|---|---|---|---|
| Filet de cadre effacé (DOC-007 p1) | F20b | audit des régions puis mesure numérique | F22, puis F22b | corrigé (1,00) |
| Cases vides effacées (DOC-007 p1) | F20 (régression latente) | relecture, recadrage | F21 | corrigé |
| Nouveau refus `p001-b0010` (DOC-007) | F20b version 1 | registre | F20b réécrit (masquage des boîtes voisines) | corrigé |
| 7 refus nouveaux | F22 version 1 (part d'encre) | registre | critère « filet continu dépassant le masque » | corrigé |
| Filet de 0,3 pt aminci (DOC-004 `p001-b0106`, 95 px) | F24 | mesure du débord de masque | non corrigé : le filet reste visible | **limitation** |
| Couverture DOC-008 −0,049 | F23 | mesure v2.1 | assumé : contenu faux retiré | volontaire |
| Caractères tentés DOC-007 −114 | F21 | mesure v2.1 | assumé : cases protégées | volontaire |

## 6. Variance de la génération Interim (run25-live)

Avec le même code et la même analyse, sans mémoire de traduction :

| Indicateur | run25 (mémoire run24) | run25-live (génération réelle) |
|---|---|---|
| Requêtes au moteur IA | 0 | 63 (gpt-5-mini) |
| Réservation maximale par requête | — | 22 467 tokens (≤ 32 768) |
| Violations de budget | 0 | 0 |
| Couverture écrite totale | 0,8419 | 0,8464 |
| Blocs dont la cible diffère à source identique | — | 333 sur 1 072 |
| Part des caractères concernés | — | 71,6 % (70,6 % mesuré en run18) |

Par document, l'écart run25-live − run25 va de −0,241 (DOC-005 : le moteur rend inchangé un long bloc, et le nombre
de caractères tentés passe de 254 à 78) à +0,020 (DOC-006). Les codes critiques varient également : DOC-005 n'a plus
de refus d'encre parce que le bloc n'est plus traduit, et DOC-006 n'a plus d'entité modifiée dans cette génération.

**Conclusion** : sans mémoire de traduction, un écart de ±0,02 à ±0,24 par document peut provenir de la seule
génération. Les gains run24 → run25 ont donc été établis à traductions identiques. La couverture plus élevée de
run25-live n'est pas un résultat du code.

## 7. Critères d'acceptation (§19)

| Critère | État | Preuve ou motif |
|---|---|---|
| Les huit documents ont été rejoués | **Oui** | run25 (verdict) et run25-live : 8 documents sur 8, empreintes SHA-256 des originaux inchangées |
| Les trois cas prioritaires ont été examinés en détail | **Oui** | relecture instrumentée bloc par bloc, registre, recadrages ouverts (liste dans `RUN25_DOCUMENT_FIDELITY_REPORT.md` §2) |
| Les régressions sont mesurées avec une méthode stable | **Oui** | `measure-v2.1-run18` et registre identiques pour les cinq jeux ; mémoire de traduction pour isoler le code |
| Les tableaux conservent leur structure | **Non mesuré par le moteur** | `no_real_table_detected` sur les 8 scans (score `TABLE` = NULL) ; indices : pages 1:1, trace des cellules identique à run24, filets mesurés ; 1 filet aminci |
| Les données critiques sont préservées | **Partiel** | 2 numéros faux retirés (F23) ; contrôle des chiffres sur 159 blocs : 0 altération ; mais entités modifiées signalées (DOC-006, DOC-002, DOC-007) : la validation automatique est bloquée |
| Les éléments graphiques sont intacts | **Partiel** | cachets, signatures et logos : 0 % ; cases DOC-004 : 0 % ; mais 81 régions altérées (toutes sous un bloc traduit) et 6 573 px d'encre effacée hors blocs écrits |
| Les défauts non résolus sont documentés | **Oui** | `LIMITATIONS.md`, `RUN25_ROOT_CAUSE_ANALYSIS.md` §4 |
| Les tests existants ne régressent pas | **Oui (local)** | 610 tests backend (591 existants + 19 nouveaux), golden 8/8, Angular 16/16, build, Ruff, pip-audit ; CI : voir `TEST_RESULTS.md` |
| Les preuves permettent de reproduire les résultats | **Oui** | `REPRODUCTION.md`, empreintes de code par run, archive privée de preuves |

**Verdict : `REVIEW_REQUIRED` pour les 8 documents. Aucun document n'est déclaré conforme ni PASS.** Les critères
« données critiques » et « éléments graphiques » ne sont que partiellement atteints. Le critère « tableaux » n'est
pas mesuré par le moteur.
