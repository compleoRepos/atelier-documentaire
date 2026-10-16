# RUN26 — Causes racines et correctifs

Ce rapport décrit, pour chaque correctif RUN26 : le symptôme, la cause, le correctif, le test ciblé, la contre-épreuve,
la preuve avant/après et les effets de bord. Les identifiants de blocs (`p001-b0041`, etc.) sont des positions dans le
document anonymisé ; aucun texte de document n'est reproduit.

Règle suivie : **aucun correctif n'a modifié la méthode de score**. Celle-ci a été gelée avant le premier correctif
(empreintes SHA-256 des quatre fichiers de méthode, recontrôlées 4/4 après chaque étape, voir
[méthodologie](RUN26-SCORE-METHODOLOGY.md), §8).

## 1. Audit préalable de RUN25

| Constat | Cause | Décision RUN26 |
|---|---|---|
| Deux tableaux RUN25 divergents (DOC-004, DOC-008, catégories OCR, couverture corpus 0,845 / 0,842) | Le premier tableau mesurait un **état intermédiaire** (run25c, avant les correctifs F23/F24) ; le second, le **verdict** (run25e). Aucun des deux ne portait l'identifiant du run mesuré | Source de vérité unique : mesure `measure-v2.1-run18` + `scorecard-1` sur les mêmes artefacts, pour tous les runs comparés. Chaque sortie porte le libellé du run et la version de méthode |
| Les rapports RUN25 versionnés citent-ils le bon état ? | Vérifié : ils citent le verdict run25e | Pas de correction des rapports RUN25 |
| Impossible de dire, pour un bloc, si sa cible venait d'un appel modèle ou d'une mémoire | Le service ne gardait que des compteurs agrégés par exécution | Correctif P0 (§2) |

## 2. P0 — Preuves de génération (appel modèle ou mémoire)

- **Symptôme.** Un rapport ne pouvait pas prouver qu'une traduction donnée provenait d'un appel réel au modèle, ni
  rapprocher les requêtes envoyées des blocs traduits.
- **Cause.** Pas de trace par requête ; pas de provenance par bloc ; une exécution qui rejouait une mémoire de
  traduction ne se distinguait pas d'une génération nouvelle.
- **Correctif** (`backend/app/ai/translation/interim.py`, `service.py`, `tools/interim_owner_corpus_run.py`) :
  - chaque requête porte un identifiant de corrélation client (en-tête `x-request-id`), un index, des horodatages de
    début et de fin, le statut HTTP et l'identifiant de réponse du fournisseur (gardé seulement s'il s'agit d'un jeton
    opaque court) ; la trace est enregistrée sur **tous** les chemins (succès, refus, redirection, erreur, délai) ;
  - chaque bloc reçoit une provenance (`block-provenance-1`) : `MODEL_CALL` (avec index et corrélation de la requête,
    et résultat `CHANGED` / `UNCHANGED` / `GUARD_REJECTED`), `MODEL_CALL_FAILED`, `NOT_SENT`, `OFFLINE_MEMORY` ou
    `TRANSLATION_MEMORY` (avec le run de la mémoire et la provenance d'origine) ;
  - rapprochement : si le nombre de requêtes envoyées diffère du nombre de traces, une alerte **critique**
    `EVIDENCE_REQUEST_COUNT_MISMATCH` est émise ;
  - `generation_mode` explicite : `NEW_MODEL_GENERATION`, `MIXED_MEMORY_AND_NEW_GENERATION`,
    `TRANSLATION_MEMORY_REUSE_ONLY`, `NO_MODEL_CALL`, `RECORDED_RESULT_REPLAY` ;
  - journal d'exécution JSONL horodaté, avec empreinte du code, HEAD Git et identifiant d'autorisation (privé).
- **Tests.** `backend/tests/unit/test_run26_traceability.py`, 13 tests (données synthétiques, transport HTTP simulé) :
  trace complète et rapprochée d'un appel réussi ; relance après découpage d'un lot (une trace par requête, chaque
  bloc pointe vers la requête qui a produit son état final) ; requête en échec tracée et jamais comptée comme
  traduite ; blocs non envoyés marqués `NOT_SENT` ; écart requêtes/traces signalé en critique ; absence de requête
  jamais présentée comme une génération ; mémoire déclarée avec sa provenance d'origine, ou `UNKNOWN_PRE_RUN26`.
  Ces tests ont été ajoutés après le run de verdict : la traçabilité n'avait jusque-là été prouvée que par le corpus.
  En les écrivant, un premier scénario a échoué : c'était le scénario qui était faux, pas le code. Le service envoie
  aussi les nombres au modèle (sous forme de marqueurs protégés), et la relance après découpage était correctement
  tracée. Ce cas est devenu un test à part entière.
- **Contre-épreuves.** Enregistrement de provenance et identifiant de réponse neutralisés (greffon pytest privé, sans
  modification du dépôt) : 8 échecs sur les 8 tests concernés. Mémoire déclarée à tort comme génération nouvelle
  (copie temporaire du lanceur) : 3 échecs sur les 3 cas avec mémoire. Les 2 cas sans mémoire passent, comme attendu.
  La contre-épreuve a aussi révélé un test trop faible (il ne vérifiait pas l'origine du bloc), qui a été renforcé.
- **Preuve sur corpus.** Run intermédiaire : 5 requêtes, 5 traces, provenance `MODEL_CALL` 18 blocs,
  `TRANSLATION_MEMORY` 973, `NOT_SENT` 81. Run de verdict : 0 requête, `TRANSLATION_MEMORY_REUSE_ONLY` ×8,
  `model_invoked = false`, et la provenance d'origine reproduit exactement les mêmes 18 / 973 / 81.
- **Limite.** Les 973 cibles de mémoire proviennent d'une génération antérieure à RUN26 : leur requête génératrice
  n'est pas traçable. C'est déclaré, pas masqué (voir [défauts ouverts](RUN26-OPEN-ISSUES.md)).

| Document | Mode de génération (verdict) | Requêtes | Provenance des blocs | Original inchangé | Violations budget |
|---|---|---|---|---|---|
| DOC-001 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 47 | oui | 0 |
| DOC-002 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 24 | oui | 0 |
| DOC-003 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 13 | oui | 0 |
| DOC-004 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 229 | oui | 0 |
| DOC-005 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 89 | oui | 0 |
| DOC-006 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 418 | oui | 0 |
| DOC-007 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 178 | oui | 0 |
| DOC-008 | `TRANSLATION_MEMORY_REUSE_ONLY` | 0 | TRANSLATION_MEMORY 74 | oui | 0 |

## 3. F25 — Texte OCR non fiable envoyé en traduction

- **Symptôme.** Des blocs dont l'OCR avait une confiance très basse (par exemple 0,19 et 0,24 sur deux blocs de
  DOC-004) étaient traduits et comptés `TRANSLATED`. Une partie de ces lectures était du bruit OCR : la « traduction »
  ne pouvait pas être fidèle.
- **Cause.** L'OCR ne relisait jamais une ligne douteuse, et rien ne bloquait l'envoi d'une lecture peu fiable au
  modèle.
- **Correctif** (`backend/app/documents/ocr_recovery.py`, intégré à `line_verification.py` version 10) : relecture de
  la ligne sur une **copie** prétraitée (variante binarisée et variante en niveaux de gris, meilleure des deux), avec
  des refus explicites :
  - pas plus fiable que la première lecture (gain de confiance insuffisant) ;
  - zone ambiguë, lecture vide, écriture de droite à gauche ;
  - **nombres différents** (mêmes chiffres exigés, séparateurs compris) ;
  - lecture plus courte que 75 % de la première (troncature) ;
  - lecture non soutenue lexicalement (moins de 50 % de mots connus et confiance < 0,90) ;
  - lecture identique : la ligne est alors « confirmée » (confiance relevée, texte inchangé).

  Un bloc encore douteux après relecture passe `UNCERTAIN` (`ocr_unreliable`) : il part en **revue humaine** au lieu
  d'être traduit à l'aveugle. L'original n'est jamais modifié.
- **Bogue trouvé par les tests pendant le développement.** Une première version comparait les lectures sans la
  ponctuation : deux montants identiques en chiffres mais avec des séparateurs différents auraient été « confirmés ».
  Corrigé (refus `numbers_disagree`) et couvert par un test.
- **Tests.** 16 tests F25 dans `test_run26_regressions.py`. Contre-épreuve : relecture neutralisée → 5 échecs.
- **Preuve sur corpus** : 123 lignes tentées, 16 récupérées, 4 confirmées, 79 blocs envoyés en revue humaine.

| Document | Pages scannées | Confiance moteur ≥ 0,80 (part des car. attendus) run25e → run26 | Lignes tentées F25 | Récupérées | Confirmées | Blocs mis en revue | Exactitude caractère |
|---|---|---|---|---|---|---|---|
| DOC-001 | 2/2 | 0,965 → 0,966 | 6 | 1 | 0 | 5 | inconnue |
| DOC-002 | 1/1 | 0,790 → 0,790 | 4 | 0 | 0 | 3 | inconnue |
| DOC-003 | 1/1 | 1,000 → 1,000 | 0 | 0 | 0 | 0 | inconnue |
| DOC-004 | 2/2 | 0,754 → 0,802 | 32 | 15 | 1 | 15 | inconnue |
| DOC-005 | 2/2 | 0,825 → 0,825 | 7 | 0 | 0 | 6 | inconnue |
| DOC-006 | 16/16 | 0,985 → 0,985 | 37 | 0 | 1 | 25 | inconnue |
| DOC-007 | 5/5 | 0,759 → 0,760 | 35 | 0 | 1 | 24 | inconnue |
| DOC-008 | 2/2 | 0,943 → 0,951 | 2 | 0 | 1 | 1 | inconnue |

- **Effets de bord, mesurés.**
  - DOC-004 : la confiance moteur pondérée passe de 0,754 à 0,802 ; la part de texte non fiable envoyée en traduction
    baisse (`no_unreliable_source_translated` 0,955 → 0,994) ; mais 3 nouveaux débordements apparaissent, sur les cibles
    plus longues des lignes récupérées (`LAYOUT_OVERFLOW` 14 → 17). Ces blocs restent `FAILED` (refus de rendu sûr).
  - La couverture écrite du corpus baisse légèrement (0,8419 → 0,8381) : texte mis en revue au lieu d'être traduit.
  - **Perte collatérale réelle** (DOC-007, `p001-b0041`) : deux voisins passés `UNCERTAIN` gardent leur source ;
    le masque ne s'étend donc plus sur eux, l'encre source résiduelle est détectée et une valeur correctement
    traduite n'est plus rendue (`FAILED: render_residual_source_ink`). Le contrôle a raison de refuser, mais c'est
    une régression de couverture causée par F25 ; elle est inscrite dans les défauts ouverts.
  - Deux blocs de DOC-004 relus par F25 (confiance passée de 0,19/0,24 à 0,94/0,91) ont été renvoyés au modèle, qui a
    rendu la source inchangée : `TRANSLATED` (faux succès) → `FAILED: model_returned_source` (échec honnête).

## 4. F26 — Un bloc « traduit » n'était pas relu dans le PDF produit

- **Symptôme.** Le statut `TRANSLATED` signifiait « une cible existe et un placement a été tenté », pas « la cible est
  lisible dans le PDF livré ».
- **Cause.** Aucune vérification après rendu du texte réellement inséré.
- **Correctif** (`backend/app/documents/render_verification.py`, `pdf_fidelity.render_pdf`, `pipeline.py`,
  `block_status.py`) : le moteur expose les placements réellement insérés ; le PDF candidat est relu dans le cadre de
  chaque placement (± 1,5 pt). Si le rappel des jetons de la cible est inférieur à 0,90, alerte critique
  `RENDER_TARGET_NOT_VERIFIED` et statut `FAILED: render_target_incomplete`.
- **Tests.** 6 tests F26 (cible complète, tronquée, hors cadre, insensibilité aux accents, scindée…).
- **Preuve sur corpus** : 487 placements, 487 vérifiés, 0 non vérifié.

| Document | Placements insérés | Vérifiés (rappel ≥ 0,90) | Non vérifiés | Non mesurables |
|---|---|---|---|---|
| DOC-001 | 9 | 9 | 0 | 0 |
| DOC-002 | 8 | 8 | 0 | 0 |
| DOC-003 | 2 | 2 | 0 | 0 |
| DOC-004 | 88 | 88 | 0 | 0 |
| DOC-005 | 3 | 3 | 0 | 0 |
| DOC-006 | 268 | 268 | 0 | 0 |
| DOC-007 | 87 | 87 | 0 | 0 |
| DOC-008 | 22 | 22 | 0 | 0 |

- **Ce que F26 a révélé.** Cinq incohérences apparentes de la mesure `render_outcome` ont été inspectées
  visuellement (planches privées). Quatre étaient des **artefacts de la mesure** : la cible était écrite en entier
  dans le cadre du moteur, plus large que la fenêtre OCR utilisée par la mesure. La cinquième (DOC-004 `p001-b0033`)
  avait une cible complète, mais incohérente : le bloc OCR mêlait deux questions et du bruit, et un filet de tableau
  traverse le texte. **Aucun contrôle automatique ne détecte ce défaut** : il est inscrit dans les défauts ouverts.

## 5. F27 — Faux « textes traduits manquants »

- **Symptôme.** Le compteur interne de l'alerte `RENDER_TRANSLATED_TEXT_MISSING` comptait des cibles absentes du PDF
  alors qu'elles y figuraient.
- **Cause.** La mesure cherchait chaque cible comme sous-chaîne contiguë d'**un seul** bloc de texte du PDF. Une cible
  écrite sur plusieurs lignes, que le PDF découpe en plusieurs blocs, était déclarée absente. Par ailleurs, des
  éléments visuels protégés, volontairement non remplacés, étaient comptés comme « traduits ».
- **Correctif** (`render_metrics.py`, `render_verification.py`, `pipeline.py`) : un bloc vérifié par F26 est présent ;
  les éléments protégés sont exclus des « traduits » ; F26 s'exécute avant les métriques de rendu.
- **Preuve sur corpus** : compteur 65 → 44 (DOC-001 3 → 1, DOC-004 34 → 21, DOC-006 10 → 6, DOC-008 5 → 3).
  Les 21 faux positifs supprimés = 17 cibles présentes mais scindées + 4 éléments visuels protégés. Les 44 restants
  correspondent aux refus de rendu réels (blocs `FAILED: render_*`). L'alerte reste présente et critique dans 7
  documents : **F27 corrige un compteur, il ne masque aucun défaut**.

## 6. F28 — Identifiant ou nombre réécrit compté « préservé »

- **Symptôme.** Un identifiant ou un nombre que le moteur avait réécrit pouvait être compté
  `PRESERVED_INTENTIONALLY`, ce qui cachait un éventuel échec de rendu.
- **Correctif** (`block_status.py`, `block-status-3`) : un identifiant/nombre réécrit suit le chemin normal
  (`TRANSLATED`, ou échec de rendu le cas échéant). `PRESERVED_INTENTIONALLY: identifier_or_number` n'est utilisé
  que si la cible est identique à la source.
- **Tests F27/F28** : 5 tests. Contre-épreuve avec F27 et F28 neutralisés : 4 échecs (le 5e test est un cas négatif,
  qui doit passer dans les deux cas).

## 7. Transitions de statut run25e → run26 (preuve d'absence de masquage)

| Document | Blocs comparés | Inchangés | Transitions de statut run25e → run26 |
|---|---|---|---|
| DOC-001 | 47 | 41 | FAILED->UNCERTAIN ×4, PRESERVED->TRANSLATED ×1, PRESERVED->UNCERTAIN ×1 |
| DOC-002 | 24 | 22 | FAILED->UNCERTAIN ×2 |
| DOC-003 | 13 | 13 | aucune |
| DOC-004 | 229 | 210 | FAILED->NOT_TRANSLATABLE ×1, FAILED->PRESERVED ×1, FAILED->TRANSLATED ×2, FAILED->UNCERTAIN ×6, NOT_TRANSLATABLE->TRANSLATED ×1, PRESERVED->TRANSLATED ×2, PRESERVED->UNCERTAIN ×3, TRANSLATED->FAILED ×2, TRANSLATED->UNCERTAIN ×1 |
| DOC-005 | 89 | 88 | FAILED->UNCERTAIN ×1 |
| DOC-006 | 418 | 399 | FAILED->UNCERTAIN ×12, PRESERVED->TRANSLATED ×1, PRESERVED->UNCERTAIN ×6 |
| DOC-007 | 178 | 160 | FAILED->UNCERTAIN ×10, PRESERVED->UNCERTAIN ×2, TRANSLATED->FAILED ×1, TRANSLATED->UNCERTAIN ×5 |
| DOC-008 | 74 | 74 | aucune |

Bilan : 9 blocs perdent `TRANSLATED` (6 vers `UNCERTAIN`, 3 vers `FAILED`), 7 le gagnent. Toutes les pertes vont vers
un statut **plus prudent** et visible ; aucune ne va vers `PRESERVED_INTENTIONALLY` ou `NOT_TRANSLATABLE`.

Deux blocs de DOC-004 passent de `FAILED` à un statut non traduit (`PRESERVED_INTENTIONALLY: proper_name_or_reference`
et `NOT_TRANSLATABLE: no_linguistic_content`). Ce sont deux anciens échecs `model_returned_source` dont la lecture
OCR était du bruit (confiance 0,31 et 0,14). F25 les a relus (confiance 0,945 et 0,94) : l'un est une référence,
l'autre une valeur purement numérique. Le reclassement découle d'une lecture correcte. Ce n'est pas un masquage.

## 8. Confidentialité : valeurs issues des documents dans le code et les tests

- **Symptôme.** Le scanner anti-fuite RUN26 (mots rares, séquences de 4 mots et nombres comparés au texte OCR et aux
  cibles du corpus) a trouvé des valeurs issues des documents :
  - dans le code RUN26, pas encore commité : un montant (deux formats), des fragments de bruit OCR et un mot tronqué
    dans une docstring ou un commentaire ; un montant, une date de naissance et des fragments OCR dans les tests ;
  - dans du code **déjà poussé** par des runs précédents : un salaire annuel brut et un capital social (commentaire
    et test), des dates de signature ou de documents (test d'entités), un numéro de téléphone (commentaire) et un
    fragment OCR (test).
- **Cause.** Pendant les analyses, des cas de test et des exemples de commentaires ont été dérivés de blocs réels.
  Aucun contrôle automatique ne comparait le dépôt au corpus privé.
- **Correctif.** Toutes ces valeurs ont été remplacées par des valeurs synthétiques de même forme (même format de
  nombre ou de date, même nombre de jetons, mots inconnus remplacés par des mots inconnus), absentes du corpus.
  Preuves : arbre syntaxique Python **identique** pour les fichiers applicatifs touchés (les commentaires seuls, ou
  les docstrings seules, ont changé : comportement inchangé) ; tests concernés passés ; nouveau scan complet du
  dépôt sans résultat hors faux positifs (compteurs, versions, années, tournures génériques, empreintes des fichiers
  de méthode).
- **Ce qui n'est pas corrigé.** L'**historique Git** des branches déjà poussées contient encore ces valeurs. Les en
  retirer exige une réécriture d'historique et un `push --force` : c'est une action destructive, qui n'a **pas** été
  faite sans décision explicite du responsable du dépôt.

## 9. Causes connues non corrigées

| Défaut | Cause identifiée | Pourquoi non corrigé dans RUN26 |
|---|---|---|
| Débordements (`LAYOUT_OVERFLOW`, `FAILED: render_overflow`) | Cible française plus longue que la zone source, police minimale atteinte | Une relance « à longueur contrainte » risque une omission indétectable sur des textes juridiques ; les blocs restent `FAILED` → revue humaine |
| Masques trop larges (`RENDER_TEXT_MASK_TOO_LARGE`, `VISUAL_MASK_TOO_LARGE`) | Masque de blanchiment débordant sur des éléments graphiques voisins | Non traité dans RUN26 |
| Encre source résiduelle (`SCAN_TEXT_OVER_SOURCE_INK`) | Texte source mal couvert sous la traduction | Non traité ; aggravé localement par F25 (§3) |
| `model_returned_source` (102 blocs) | Le modèle renvoie la source inchangée | Nécessite une analyse par langue et un moteur qualifié (Qwen) |
| Régions protégées altérées, entités modifiées | Voir défauts ouverts | Non traité dans RUN26 |
