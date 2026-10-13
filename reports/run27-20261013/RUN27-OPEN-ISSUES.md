# RUN27 — Défauts et limites ouverts

> **Le seuil de 94/100 n’est pas atteint** : 65,9 pour le corpus (borne basse officielle, v2), 73,4 au mieux pour un document (DOC-006). **Aucun document n’est `VALIDATED` ; tous restent `REVIEW_REQUIRED`.** La mise en production et toute déclaration de conformité restent bloquées.

## 1. Pourquoi 94 est inaccessible aujourd’hui

- Plafond de la borne basse = 100 − points inconnus : **76,8** par document (68,5 pour DOC-003), **75,8** pour le corpus. 94 > 75,8.
- Les points inconnus proviennent **uniquement** des références humaines absentes (4 sous-composantes par document) ; aucune mesure automatique ne manque.
- Condition nécessaire, non suffisante : exécuter le pack de validation humaine (RUN27-HUMAN-VALIDATION-PACK.md, 1 072 lignes, 0 revue). Même avec des références parfaites, chaque défaut critique ouvert maintient `REVIEW_REQUIRED`.

## 2. Défauts critiques ouverts (run27)

| Id / code | Document(s) | Occurrences | Impact | Correction nécessaire |
| --- | --- | --- | --- | --- |
| **MV-01** identifiant altéré par rapport à l’image | DOC-005 | 1 | identifiant faux dans le PDF (régression RUN27, invisible aux métriques) | relecture OCR ciblée des identifiants, ou référence humaine ; contrôles d’entités contre l’image et non contre l’OCR |
| `LAYOUT_OVERFLOW` | DOC-004 16, DOC-006 3, DOC-007 7, DOC-008 2 | 28 | blocs non traduits (`FAILED render_overflow`), original conservé | croissance verticale contrôlée dans un blanc vérifié ; réduction de police sous contrainte de lisibilité ; sinon revue humaine |
| `PROTECTED_REGION_CHANGED` | DOC-004 | 6 | régions visuelles protégées modifiées par le rendu | diagnostic région par région (tampon, logo, signature) ; exclusion des masques |
| `RENDER_SOURCE_TEXT_MISSING` / `RENDER_TEXT_CLIPPED_OR_MISSING` / `RENDER_TRANSLATED_TEXT_MISSING` | DOC-001, 002, 004, 006, 007, 008 | 6 × 3 familles (1 par document) | texte source ou cible absent d’une zone rendue | analyse bloc par bloc ; une partie relève de PDF textuellement scindés |
| `SCAN_TEXT_OVER_SOURCE_INK` | DOC-002, DOC-006 | 2 | rendu refusé pour encre source résiduelle (original conservé) | dans DOC-006, la zone touche un tampon coloré : la garde F31 interdit volontairement le masquage |
| `UNMAPPED_TABLE_CONTENT` | DOC-007 | 1 | contenu de tableau non rattaché à une cellule | reconstruction de la structure du tableau |

Total : 55 alertes critiques mesurées et 1 défaut critique vérifié à l’œil.

## 3. Défauts majeurs et limites du produit

| Sujet | Constat | Correction nécessaire |
| --- | --- | --- |
| MV-03 — mots source résiduels dans une ligne traduite | DOC-007 : ligne justifiée découpée en blocs de mots, une partie traduite et une partie non | segmentation au niveau ligne avant traduction |
| Blocs refusés par les gardes | DOC-006 : l’ordinal reste non traduit (le modèle redonne une forme invalide, refusée par F34) ; d’autres blocs `FAILED` pour garde d’entités | consigne de traduction des ordinaux, ou post-édition humaine |
| Blocs OCR non fiables | 150 blocs `UNCERTAIN` sur le corpus (original conservé, revue humaine) | OCR de meilleure qualité, ou transcription humaine |
| Langue détectée erronée sur une ligne déjà française (cause de MV-01) | une ligne française d’un pied de page est détectée comme une autre langue | lisser la langue à partir des voisins **sans** provoquer d’omission silencieuse (risque non maîtrisé : non fait) |
| Élément visuel protégé envoyé au modèle | DOC-006 : cible stockée mais non rendue (aucun effet sur le PDF) | court-circuiter l’envoi des blocs protégés |
| Écritures de droite à gauche | non qualifiées sur un rendu dédié | jeu de tests RTL |
| Couverture faible | DOC-005 21,3 %, DOC-002 64,4 %, DOC-001 58,8 %, DOC-008 59,1 % de caractères écrits | dépend des corrections ci-dessus et de la revue |

## 4. Limites de la mesure

- **Entités comparées à l’OCR** : une erreur d’OCR reproduite par la cible n’est pas vue (MV-01), et une cible juste peut être pénalisée. Le gain de DOC-005 (+8,33 points sur les entités) en est un artefact.
- **Défauts visibles mais non mesurés** : l’état des cases à cocher (MV-02), les mots résiduels (MV-03) et les identifiants altérés n’ont été trouvés que par contrôle visuel. Une mesure image-à-image ciblée serait nécessaire.
- **Dépendance de la mesure au code produit** : désormais tracée par `ruler_fingerprint.py`. Toute comparaison entre runs doit se faire à empreinte de règle identique.
- **v1** : le plafond codé en dur (84,2) était faux et les preuves ajoutaient des points. La v1 n’est conservée que pour la reproductibilité historique.

## 5. Prérequis hors périmètre RUN27

- Relecteurs bilingues autorisés et signature (pack humain).
- Qwen / vLLM privé : non qualifié dans ce run ; Interim est un moteur temporaire, sans repli public automatique. Aucune conclusion de qualité de Qwen ne peut être tirée de RUN27.
- Validation bancaire ou réglementaire : non effectuée.
