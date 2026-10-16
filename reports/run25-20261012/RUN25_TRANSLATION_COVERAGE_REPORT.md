# RUN25 — Rapport de couverture de traduction

Ce rapport mesure ce qui a été traduit, ce qui a été écrit dans le PDF, ce qui ne l'a pas été et pourquoi (prompts
run25 §3, §6, §12 et §16). Les chiffres proviennent de l'export anonymisé `metrics/RUN25_METRICS_BY_DOCUMENT.json`
(méthode `measure-v2.1-run18`) et de `metrics/RUN25_LIVE_GENERATION_CHECK.json`.

## 1. Définitions

| Grandeur | Définition |
|---|---|
| Caractères attendus | caractères source des blocs dans le périmètre de traduction, recalculés avec **une seule règle de langue** pour tous les runs (preuve lexicale, et non l'étiquette propre au run) |
| Caractères tentés | caractères attendus pour lesquels le run a produit une cible |
| Caractères écrits | caractères attendus dont la cible est retrouvée **écrite** dans le PDF produit (extraction indépendante du texte) |
| Partiels / absents | caractères tentés retrouvés seulement en partie, ou pas du tout, dans le PDF |
| **Couverture tentée** | tentés / attendus. Elle correspond à la « couverture stricte » historique du 09/10 : tout bloc non français non traduit compte comme manquant, quelle qu'en soit la raison |
| **Couverture écrite** | écrits / attendus. C'est la couverture stricte côté rendu |
| Hors périmètre | caractères exclus du dénominateur : déjà en français, identiques en français, identifiants, noms propres, contenu non linguistique |

Les valeurs du 09/10 ne sont **pas** comparables à celles-ci : la règle du dénominateur a changé en run18. Les cinq
jeux de ce rapport (baseline, run17, run24, run25a, run25) sont mesurés avec la même méthode.

## 2. Couverture par document

| Document | Tentée : base / run17 / run24 / run25 | Écrite : base / run17 / run24 / run25 |
|---|---|---|
| DOC-001 | 0,633 / 0,587 / 0,729 / 0,729 | 0,598 / 0,555 / 0,576 / 0,576 |
| DOC-002 | 0,607 / 0,449 / 0,555 / 0,555 | 0,434 / 0,273 / 0,393 / 0,393 |
| DOC-003 | 0,000 / 0,741 / 0,741 / 0,741 | 0,000 / 0,741 / 0,741 / 0,741 |
| DOC-004 | 0,869 / 0,730 / 0,862 / 0,852 | 0,717 / 0,361 / 0,538 / **0,589** |
| DOC-005 | 0,696 / 0,155 / 0,694 / 0,694 | 0,044 / 0,155 / 0,454 / 0,454 |
| DOC-006 | 0,936 / 0,961 / 0,945 / 0,945 | 0,913 / 0,953 / 0,937 / 0,937 |
| DOC-007 | 0,903 / 0,906 / 0,896 / 0,884 | 0,796 / 0,710 / 0,763 / **0,778** |
| DOC-008 | 0,590 / 0,792 / 0,771 / 0,722 | 0,547 / 0,646 / 0,640 / 0,591 |
| **Total** | 38 597 / 38 588 / 39 007 / 38 773 car. tentés | **0,8365 / 0,8195 / 0,8364 / 0,8419** |

* **Pourquoi la couverture tentée baisse alors que la couverture écrite monte** :
  * DOC-004 et DOC-008 : F23 retire des blocs dont la source OCR était fausse (numéros inversés) ;
  * DOC-007 : F21 retire une ligne d'options aux cases mal lues.

  Ces blocs ne sont plus envoyés au moteur IA. Dans le même temps, F20, F20b et F24 font écrire des traductions qui
  étaient auparavant refusées au rendu.
* L'écart entre couverture tentée et couverture écrite correspond aux traductions produites mais **non écrites**
  (refus de rendu sûrs, §5). Il n'est pas masqué.
* DOC-003 : la baseline réécrivait du français hors périmètre ; sa valeur 0 n'est pas comparable.

## 3. Caractères du run final

| Document | Attendus | Tentés | Écrits | Partiels | Absents | Absents run24 |
|---|---|---|---|---|---|---|
| DOC-001 | 606 | 442 | 349 | 0 | 93 | 93 |
| DOC-002 | 820 | 455 | 322 | 0 | 133 | 133 |
| DOC-003 | 81 | 60 | 60 | 0 | 0 | 0 |
| DOC-004 | 3 437 | 2 927 | 2 024 | 99 | 804 | 1 014 |
| DOC-005 | 366 | 254 | 166 | 0 | 88 | 88 |
| DOC-006 | 26 942 | 25 448 | 25 242 | 45 | 161 | 168 |
| DOC-007 | 8 974 | 7 930 | 6 981 | 82 | 867 | 1 118 |
| DOC-008 | 1 741 | 1 257 | 1 029 | 0 | 228 | 228 |
| **Total** | **42 967** | **38 773** | **36 173** | **226** | **2 374** | 2 842 |

Français déjà présent réécrit : **0 caractère** dans les 8 documents (run24 et run25).

## 4. Classification de chaque bloc non traduit (§3 et §6)

Chaque bloc dont le statut n'est pas `TRANSLATED` est rangé dans l'une des cinq catégories du prompt à partir de son
statut et de son motif moteur. La correspondance est fixée dans l'outil d'export, et un motif non prévu provoque une
erreur au lieu d'un classement par défaut.

| Catégorie du prompt | Statuts et motifs moteur |
|---|---|
| Déjà en français | `PRESERVED_INTENTIONALLY:already_french`, `:identical_in_french` |
| Identifiant ou donnée à préserver | `PRESERVED_INTENTIONALLY:identifier_or_number`, `:proper_name_or_reference`, `:protected_visual_element`, `NOT_TRANSLATABLE:no_linguistic_content` |
| Texte non lisible | `UNCERTAIN:ocr_unreliable`, `UNCERTAIN:ocr_script_inconsistent` |
| Bloc réellement oublié | `NOT_PROCESSED` |
| Revue humaine nécessaire | `UNCERTAIN:form_structure_ambiguous`, `FAILED:model_returned_source`, `:entity_guard_rejected`, `:render_overflow`, `:render_residual_source_ink`, `:render_mask_unsafe`, `:render_rtl_shaping_unsupported` |

Run final (blocs / caractères) :

| Document | Déjà en français | Identifiant ou donnée | Non lisible | Réellement oublié | Revue humaine |
|---|---|---|---|---|---|
| DOC-001 | 10 / 502 | 21 / 163 | 0 / 0 | 0 / 0 | 8 / 309 |
| DOC-002 | 1 / 37 | 4 / 20 | 2 / 6 | 0 / 0 | 9 / 498 |
| DOC-003 | 10 / 573 | 0 / 0 | 0 / 0 | 0 / 0 | 1 / 21 |
| DOC-004 | 6 / 25 | 50 / 247 | 46 / 302 | 0 / 0 | 41 / 1 012 |
| DOC-005 | 48 / 1 678 | 27 / 133 | 2 / 5 | 0 / 0 | 9 / 195 |
| DOC-006 | 18 / 155 | 44 / 190 | 20 / 81 | 0 / 0 | 69 / 1 510 |
| DOC-007 | 5 / 32 | 27 / 162 | 9 / 156 | 0 / 0 | 44 / 1 751 |
| DOC-008 | 23 / 980 | 9 / 52 | 2 / 92 | 0 / 0 | 18 / 616 |

* **Aucun bloc réellement oublié** : tous les blocs ont reçu un statut explicite.
* La catégorie « non lisible » regroupe aussi des blocs lisibles mais **non fiables** (sous-raisons de
  `ocr_unreliable` ci-dessous). Ces blocs sont conservés en original faute d'OCR fiable : il ne s'agit pas de texte
  illisible au sens strict.

| Document | `low_confidence_ocr` | `bidi_number_order_unreliable` (F23) | `checkbox_glyph_fused` | `checkbox_line_mixed_script_noise` | `checkbox_misread_undetected` (F21) |
|---|---|---|---|---|---|
| DOC-002 | 2 | — | — | — | — |
| DOC-004 | 34 | 2 | 7 | 2 | — |
| DOC-005 | 2 | — | — | — | — |
| DOC-006 | 20 | — | — | — | — |
| DOC-007 | 5 | — | — | — | 1 |
| DOC-008 | 1 | 1 | — | — | — |

* La catégorie « revue humaine » rassemble les refus. **Un refus n'est pas une correction réussie** (§3) : ces blocs
  restent signalés, avec leur traduction proposée conservée dans `translation.json`.

## 5. Statuts par bloc et motifs

| Document | TRANSLATED | PRESERVED_INTENTIONALLY | NOT_TRANSLATABLE | UNCERTAIN | FAILED | NOT_PROCESSED |
|---|---|---|---|---|---|---|
| DOC-001 | 8 (=) | 21 | 10 | 1 | 7 | 0 |
| DOC-002 | 8 (=) | 3 | 2 | 2 | 9 | 0 |
| DOC-003 | 2 (=) | 10 | 0 | 0 | 1 | 0 |
| DOC-004 | 86 (82) | 15 | 41 | 46 (45) | 41 (46) | 0 |
| DOC-005 | 3 (=) | 50 | 25 | 4 | 7 | 0 |
| DOC-006 | 267 (266) | 26 | 36 | 26 | 63 (64) | 0 |
| DOC-007 | 93 (87) | 10 | 22 | 12 (11) | 41 (48) | 0 |
| DOC-008 | 22 (23) | 27 | 5 | 2 (1) | 18 | 0 |

Valeur run24 entre parenthèses quand elle diffère ; (=) signifie identique.

Motifs des caractères non tentés et des caractères partiels ou absents, documents prioritaires :

| Document | Non tentés (car.) | Partiels ou absents (car.) |
|---|---|---|
| DOC-004 | `UNCERTAIN:ocr_unreliable` 224 ; `FAILED:model_returned_source` 264 ; élément visuel protégé 17 ; script OCR incohérent 5 | absent : débordement 517, encre résiduelle 135, masque dangereux 49, mise en forme RTL non prise en charge 47, élément protégé 11, **traduit et placé mais introuvable 45** ; partiel : traduit et placé 99 |
| DOC-005 | `FAILED:model_returned_source` 93 ; structure de formulaire ambiguë 14 ; OCR non fiable 5 | absent : encre résiduelle 88 |
| DOC-007 | `FAILED:model_returned_source` 537 ; structure de formulaire ambiguë 188 ; entité rejetée par le garde-fou 159 ; OCR non fiable 133 ; script incohérent 23 ; élément protégé 4 | absent : encre résiduelle 497, débordement 354, masque dangereux 16 ; partiel : traduit et placé 82 |
| DOC-008 | `FAILED:model_returned_source` 388 ; OCR non fiable 92 ; élément protégé 4 | absent : débordement 193, masque dangereux 35 |

* En DOC-008, `FAILED:model_returned_source` ne couvre que des noms, adresses, sociétés et domaines : le moteur IA les
  a conservés à juste titre. Le moteur les classe pourtant `FAILED`, faute d'un détecteur de noms propres assez large
  (voir `LIMITATIONS.md`).
* DOC-005 : la consigne de ne pas augmenter la couverture en traduisant des références ou des noms propres est
  respectée. Il y a 27 identifiants et données conservés, et 1 678 caractères français non retraduits.

## 6. Moteur IA et budget de 32K

| Run | Moteur | Requêtes | Réservation maximale | Usage total | Violations |
|---|---|---|---|---|---|
| run25 (verdict) | mémoire de traduction de run24 (signature de contenu identique) | **0** | — | — | 0 |
| run25-live (supplémentaire) | Interim gpt-5-mini, sans mémoire | 63 | 22 467 tokens | 74 580 tokens | **0** |

* La garde est inchangée : entrée bornée à 22 000 tokens (tokeniseur o200k et encadrement), complétion d'au plus
  8 000 tokens et marge de 2 768, soit un total de 32 768. Le contrôle après usage est fail-closed.
* Les requêtes de run25-live par document sont : DOC-001 2, DOC-002 2, DOC-003 2, DOC-004 11, DOC-005 2,
  DOC-006 30, DOC-007 10, DOC-008 4.
* L'usage de Interim sur les 8 originaux repose sur l'autorisation du propriétaire, conservée hors Git, liée à la liste
  des empreintes SHA-256 et expirante. Elle a été revérifiée avant chaque run.
* **Interim n'est pas une validation de Qwen.** L'abstraction vLLM/Qwen est inchangée, sans repli public automatique.

## 7. Variance de la génération

À source identique, 333 blocs sur 1 072 (37 912 caractères sur 52 977, soit **71,6 %**) reçoivent une cible
différente entre la mémoire run24 et la génération run25-live. En run18, ce taux était de 70,6 %. La couverture écrite
totale de run25-live vaut 0,8464, contre 0,8419 pour le verdict.

| Document | Écrite run25 | Écrite run25-live | Écart |
|---|---|---|---|
| DOC-001 | 0,576 | 0,586 | +0,010 |
| DOC-002 | 0,393 | 0,374 | −0,019 |
| DOC-003 | 0,741 | 0,741 | 0,000 |
| DOC-004 | 0,589 | 0,560 | −0,029 |
| DOC-005 | 0,454 | 0,213 | −0,241 |
| DOC-006 | 0,937 | 0,957 | +0,020 |
| DOC-007 | 0,778 | 0,764 | −0,014 |
| DOC-008 | 0,591 | 0,577 | −0,014 |

L'écart de DOC-005 vient d'un long bloc rendu inchangé par le moteur IA : le nombre de caractères tentés passe de
254 à 78. Le retry existant ne l'a pas récupéré.

Les écarts de cette ampleur proviennent de la génération et non du code. Le verdict reste donc run25, à mémoire
identique.

## 8. Ce que ce rapport ne prouve pas

* L'exactitude des traductions : **aucune référence humaine** n'est disponible, et aucune métrique de qualité
  linguistique (CER, WER, BLEU ou autre) n'est calculée ni présentée.
* La fiabilité de l'OCR des blocs traduits : 48 blocs traduits et écrits ont une OCR de faible confiance (§7 du
  rapport de fidélité).
* La conformité métier ou bancaire : **non validée**. Les 8 documents sont `REVIEW_REQUIRED`.
