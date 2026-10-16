# RUN18 — Rapport de couverture de traduction

Verdict run18 = passage `run24` (empreinte du code `4d4956273c97d866`). Méthode de mesure
`measure-v2.1-run18` (`tools/recette/measure_v2.py`), appliquée à l'identique à la baseline, à run17 et à
run18. Chiffres complets par document : `metrics/RUN18_METRICS_BY_DOCUMENT.json` (compteurs anonymisés).

## 1. Définitions

| Terme | Définition |
|---|---|
| Attendu | caractères des blocs source à traduire ; décidé sur le texte source seul, même règle pour tous les runs |
| Hors périmètre | déjà en français, identique en français, identifiant ou nombre, nom propre ou référence, sans contenu linguistique |
| Tenté | attendu pour lequel le run a produit une cible différente de la source |
| Écrit | tenté dont les mots de la cible sont retrouvés dans le PDF rendu près du bloc (rappel ≥ 0,85) |
| Partiel | rappel entre 0,25 et 0,85 |
| Absent | tenté mais rappel < 0,25 (traduction refusée au rendu et signalée, source visible) |
| Non tenté | attendu sans cible différente (retour inchangé du moteur, garde, OCR non fiable…) |

Couverture tentée = tenté / attendu ; couverture écrite = écrit / attendu. Seule la couverture **écrite**
reflète ce que voit le lecteur.

## 2. Couverture par document (run18)

| Document | Attendu | Tenté | Écrit | Partiel | Absent | Non tenté | Couv. tentée | Couv. écrite |
|---|---|---|---|---|---|---|---|---|
| DOC-001 | 606 | 442 | 349 | 0 | 93 | 164 | 0,729 | 0,576 |
| DOC-002 | 820 | 455 | 322 | 0 | 133 | 365 | 0,555 | 0,393 |
| DOC-003 | 81 | 60 | 60 | 0 | 0 | 21 | 0,741 | 0,741 |
| DOC-004 | 3 437 | 2 962 | 1 849 | 99 | 1 014 | 475 | 0,862 | 0,538 |
| DOC-005 | 366 | 254 | 166 | 0 | 88 | 112 | 0,694 | 0,454 |
| DOC-006 | 26 942 | 25 448 | 25 235 | 45 | 168 | 1 494 | 0,945 | 0,937 |
| DOC-007 | 8 974 | 8 044 | 6 844 | 82 | 1 118 | 930 | 0,896 | 0,763 |
| DOC-008 | 1 741 | 1 342 | 1 114 | 0 | 228 | 399 | 0,771 | 0,640 |
| **Total** | **42 967** | **39 007** | **35 939** | **226** | **2 842** | **3 960** | **0,908** | **0,836** |

Comparaison des totaux (même méthode) :

| Run | Attendu | Écrit | Partiel | Absent | Couverture écrite |
|---|---|---|---|---|---|
| baseline | 43 085 | 36 039 | 216 | 2 342 | 0,8365 |
| run17 | 42 652 | 34 955 | 292 | 3 341 | 0,8195 |
| run18 | 42 967 | 35 939 | 226 | 2 842 | 0,8364 |

Passages intermédiaires (diagnostic, pas verdict) : run18a 0,8555 (sans les correctifs de fidélité F9–F19 ;
liste reflowée, case masquée, coupures intra-mot, parenthèses miroir), run19 0,8399, run21 0,8416,
run22 0,8406, run23 0,8391. La baisse run18a → verdict est le prix des corrections de fidélité et des
refus fail-closed : elle n'est pas masquée.

## 3. Raisons des caractères non écrits (run18)

| Document | Non tentés (raison : caractères) | Partiels / absents (raison : caractères) |
|---|---|---|
| DOC-001 | structure de formulaire ambiguë 140 ; renvoyé inchangé 24 | absent, façonnage RTL non supporté 93 |
| DOC-002 | garde d'entités 206 ; renvoyé inchangé 159 | absent, masque dangereux 133 |
| DOC-003 | renvoyé inchangé 21 | — |
| DOC-004 | renvoyé inchangé 264 ; OCR non fiable 154 ; structure ambiguë 35 ; élément visuel protégé 17 ; écriture OCR incohérente 5 | absent : débordement 455, encre résiduelle 345, masque dangereux 111, RTL 47, placé mais non retrouvé 45, protégé 11 ; partiel 99 |
| DOC-005 | renvoyé inchangé 93 ; structure ambiguë 14 ; OCR non fiable 5 | absent, encre résiduelle 88 |
| DOC-006 | renvoyé inchangé 970 ; structure ambiguë 367 ; OCR non fiable 71 ; garde d'entités 55 ; protégé 31 | absent : débordement 66, RTL 30, placé mais non retrouvé 28, protégé 26, encre résiduelle 14, masque 4 ; partiel 45 |
| DOC-007 | renvoyé inchangé 537 ; structure ambiguë 188 ; garde d'entités 159 ; écriture OCR incohérente 23 ; OCR non fiable 19 ; protégé 4 | absent : encre résiduelle 732, débordement 354, masque dangereux 32 ; partiel 82 |
| DOC-008 | renvoyé inchangé 388 ; OCR non fiable 7 ; protégé 4 | absent : débordement 193, masque dangereux 35 |

« Renvoyé inchangé » = le moteur temporaire a rendu la source malgré la reprise unique (F3) : 2 456
caractères sur le corpus, première cause de non-traduction. C'est une limite du moteur temporaire Interim,
mesurée et visible, pas une omission silencieuse du pipeline.

## 4. Statut explicite par bloc (prompt §10)

Chaque bloc porte un statut et une raison (`block_status.py`, F7). Nombre de blocs run17 → run18 :

| Document | TRANSLATED | PRESERVED_INTENTIONALLY | NOT_TRANSLATABLE | UNCERTAIN | FAILED | NOT_PROCESSED |
|---|---|---|---|---|---|---|
| DOC-001 | 6 → 8 | 20 → 21 | 13 → 10 | 1 → 1 | 7 → 7 | 0 → 0 |
| DOC-002 | 8 → 8 | 5 → 3 | 5 → 2 | 2 → 2 | 15 → 9 | 0 → 0 |
| DOC-003 | 2 → 2 | 10 → 10 | 0 → 0 | 0 → 0 | 1 → 1 | 0 → 0 |
| DOC-004 | 54 → 82 | 19 → 15 | 43 → 41 | 41 → 45 | 68 → 46 | 0 → 0 |
| DOC-005 | 2 → 3 | 56 → 50 | 27 → 25 | 3 → 4 | 8 → 7 | 0 → 0 |
| DOC-006 | 273 → 266 | 28 → 26 | 41 → 36 | 31 → 26 | 61 → 64 | 0 → 0 |
| DOC-007 | 91 → 87 | 24 → 10 | 28 → 22 | 15 → 11 | 64 → 48 | 0 → 0 |
| DOC-008 | 24 → 23 | 27 → 27 | 6 → 5 | 1 → 1 | 18 → 18 | 0 → 0 |

Les statuts run17 sont recalculés sur les sorties run17 avec la même fonction (run17 ne les produisait pas).
Aucun bloc `NOT_PROCESSED` : tous les blocs ont été analysés. Distinction des cas non traduits
(prompt §10) :

| Cas | Statut / raison |
|---|---|
| Nom propre, référence (renvoyé inchangé, preuve lexicale de nom) | PRESERVED_INTENTIONALLY / `proper_name_or_reference` |
| Identifiant, nombre | PRESERVED_INTENTIONALLY / `identifier_or_number` |
| Contenu déjà en français, identique en français | PRESERVED_INTENTIONALLY / `already_french`, `identical_in_french` |
| Élément visuel protégé (cachet, logo, signature…) | PRESERVED_INTENTIONALLY / `protected_visual_element` |
| Texte de formulaire à structure ambiguë | UNCERTAIN / `form_structure_ambiguous` |
| Fragment OCR incertain | UNCERTAIN / `ocr_unreliable`, `ocr_script_inconsistent` |
| Sans contenu linguistique | NOT_TRANSLATABLE / `no_linguistic_content` |
| Bloc absent du résultat | NOT_PROCESSED / `absent_from_translation_result` (0 dans le verdict) |
| Véritable omission | FAILED / `model_returned_source`, `entity_guard_rejected`, `render_*` |

Hors périmètre run18 (caractères) : déjà français 3 767, identique en français 450, identifiant/nombre 161,
nom propre/référence 379, sans contenu linguistique 420.

## 5. Gains et reculs par rapport à run17

| Document | Écrit run17 → run18 | Principales causes du changement |
|---|---|---|
| DOC-001 | 310 → 349 | segmentation (F1, F2) ; aucun bloc écrit en run17 perdu |
| DOC-002 | 208 → 322 | encre résiduelle levée (F1) |
| DOC-003 | 60 → 60 | inchangé |
| DOC-004 | 1 250 → 1 849 | F1, F2/F2b, F3, F5, F12 ; refus volontaires F13b/F18 (OCR non fiable) |
| DOC-005 | 36 → 166 | périmètre corrigé (F4) |
| DOC-006 | 25 653 → 25 235 | blocs nouvellement segmentés renvoyés inchangés par Interim ; débordements signalés (rapport de régression §4) |
| DOC-007 | 6 316 → 6 844 | F1 (encre −414 car.) ; F19 transforme des superpositions en débordements signalés (−100 car.) |
| DOC-008 | 1 122 → 1 114 | un partiel devient débordement signalé |

## 6. Moteur et budget 32K

* Moteur réellement utilisé : **Interim**, `served_model` gpt-5-mini (moteur temporaire de développement) ;
  tracé dans chaque résumé d'exécution. Ce ne sont pas des résultats Qwen. Aucun repli public automatique.
* Le verdict n'a envoyé aucune requête : toutes les cibles proviennent de la mémoire de traduction F16
  (signature de contenu identique). Leur origine :

| Passage | Requêtes | Réservation maximale (tokens) | Violations |
|---|---|---|---|
| run19 | 59 | 22 467 | 0 |
| run21 | 1 | 16 547 | 0 |
| run22 | 1 | 16 601 | 0 |
| run23, run24 | 0 | — | 0 |

* Limite appliquée par requête : entrée ≤ 22 000 tokens (o200k + cadrage), complétion ≤ 8 000, marge 2 768,
  total ≤ 32 768 ; contrôle avant envoi et après réponse (usage), circuit ouvert en cas de dépassement.
