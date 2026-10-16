# Rapport de couverture de traduction — par document (09/10)

## 1. Définitions (identiques des deux côtés)

Toutes les valeurs sont calculées par `tools/recette/measure_corpus_metrics.py` sur la baseline (passage du 08/10) et sur le passage final run17 (empreinte `f69a6210b29e8196`), avec les mêmes règles.

- **Besoin** : nombre de caractères des blocs source détectés **non français**.
- **Bloc traduit** : la cible existe, n’est pas vide et diffère de la source **au-delà de la typographie**. Une sortie qui ne diffère que par des espaces insécables, la ponctuation ou la casse n’est pas une traduction (D27). La règle est appliquée rétroactivement à la baseline : sa couverture stricte passe ainsi de 0.8862 à 0.8810.
- **Couverture stricte (modèle)** : caractères traduits / besoin. Tout bloc non français non traduit compte comme manquant, **quelle que soit la raison**, y compris une garde volontaire ou une protection.
- **Couverture écrite dans le PDF** : caractères traduits **et retrouvés dans le PDF candidat** / besoin. C’est la mesure la plus proche de ce que lit l’utilisateur.
- **Couverture texte** : couverture stricte, en excluant des deux côtés les lignes d’identifiants seuls (règle D13 de l’application).
- **Manquant silencieux** : bloc traduit, non écrit dans le PDF et sans aucune alerte. Il doit valoir 0.

La qualité linguistique **n’est pas mesurée** : aucune traduction de référence n’a été validée par un humain, et le score de traduction vaut `NULL`. Une couverture élevée ne prouve donc pas une traduction correcte.

## 2. Couverture par document (baseline → final)

| Doc | Couverture stricte (modèle) | Couverture écrite dans le PDF | Couverture texte (identifiants exclus) | Car. source | Car. traduits | Écrits / traduits | Manquants silencieux | Statut |
|---|---|---|---|---|---|---|---|---|
| DOC-001 | 0.5925 → 0.4846 | 0.5600 → 0.4139 | 0.6077 → 0.5070 | 1 333 | 474 → 363 | 0.8540 | 0 | REVIEW_REQUIRED |
| DOC-002 | 0.6056 → 0.4275 | 0.4504 → 0.2850 | 0.6056 → 0.4402 | 872 | 519 → 357 | 0.6667 | 0 | REVIEW_REQUIRED |
| DOC-003 | 0.0000 → 0.5379 | 0.0000 → 0.5379 | 0.0000 → 0.5379 | 665 | 0 → 71 | 1.0000 | 0 | REVIEW_REQUIRED |
| DOC-004 | 0.8312 → 0.6707 | 0.6829 → 0.3748 | 0.8410 → 0.6830 | 3 830 | 3 211 → 2 564 | 0.5589 | 0 | REVIEW_REQUIRED |
| DOC-005 | 0.4244 → 0.0828 | 0.0271 → 0.0828 | 0.5663 → 0.1045 | 2 172 | 188 → 42 | 1.0000 | 0 | REVIEW_REQUIRED |
| DOC-006 | 0.9299 → 0.9523 | 0.9127 → 0.9477 | 0.9318 → 0.9545 | 27 315 | 25 122 → 25 969 | 0.9952 | 0 | REVIEW_REQUIRED |
| DOC-007 | 0.9002 → 0.8911 | 0.8115 → 0.7133 | 0.9019 → 0.8995 | 9 144 | 8 309 → 8 079 | 0.8005 | 0 | REVIEW_REQUIRED |
| DOC-008 | 0.5703 → 0.7690 | 0.5512 → 0.6843 | 0.5724 → 0.7719 | 2 786 | 1 047 → 1 398 | 0.8898 | 0 | REVIEW_REQUIRED |
| **Total** | **0.8810 → 0.8788** | **0.8305 → 0.8065** | **0.8861 → 0.8865** | 48 117 | 38 870 → 38 843 | 0.9178 | **0** | 8 × REVIEW_REQUIRED |

Lecture par document :

- **DOC-006 et DOC-008 (en hausse).** Regroupement des lignes OCR en paragraphes (D1) et suppression des fausses zones protégées sur les lignes surlignées (D4, D5).
- **DOC-003 (document français).** Les 71 caractères « traduits » sont des fragments courts (en-tête, titre, date) détectés à tort comme non français, puis réécrits (limite 7 de l’audit). Ce n’est pas un gain de traduction réel.
- **DOC-004 (en baisse).** Principal arbitrage du corpus. La garde de structure (D6, D23) laisse en source 394 caractères de cellules traversées par des filets. La garde d’OCR peu fiable (D9, D25) en laisse 172. Les gardes de rendu (D16, D20, D24) écartent une partie des traductions plutôt que de les superposer : la couverture écrite passe de 0.6829 à 0.3748. Chaque bloc concerné est signalé.
- **DOC-005 (document français).** La couverture stricte de 0.0828 est **pessimiste**. 31 fragments courts sont détectés non français : 29 font au plus 3 mots, le plus long 6, sans mot-outil étranger. Ce sont probablement des noms, adresses ou codes, que le modèle laisse inchangés. La valeur baseline (0.4244, ou 0.7494 avant D27) était gonflée par des variantes typographiques comptées comme traductions (limite 14).
- **DOC-001 et DOC-002 (en baisse).** Lignes d’identifiants laissées en source (D13) et cellules préservées par la garde de structure (DOC-001 : 140 caractères). La couverture texte, qui exclut les identifiants, baisse moins.
- **DOC-007 (stable).** Couverture stricte stable, couverture écrite en baisse (0.8115 → 0.7133) : items écartés sur encre source (D20) et débordements de cellules étroites, tous signalés.

## 3. Raisons de non-traduction (caractères)

Chaque caractère non français non traduit est classé dans une seule raison. Total : 5 250 en baseline et 5 357 en final.

| Raison | Baseline | Final | Correctif / code |
|---|---|---|---|
| Signalé non traduit (`UNTRANSLATED` et assimilés) | 4 262 | 3 202 | Reprise unique D8 ; écho typographique D27 |
| Préservé par la garde de structure formulaire/tableau | — | 1 158 | D6, D23 (`FORM_STRUCTURE_PRESERVED`) |
| Ligne d’identifiants seuls | — | 338 | D13 (`IDENTIFIER_ONLY_KEPT`) |
| OCR peu fiable (non envoyé) | — | 335 | D9, D25 (`OCR_UNRELIABLE_NOT_TRANSLATED`) |
| Protégé (entité ou zone) | 726 | 157 | D4, D5 : moins de fausses protections |
| Inchangé sans alerte spécifique | 262 | 121 | Depuis D27, 3 blocs seulement contiennent des lettres (limite 13) |
| Écriture minoritaire incohérente | — | 36 | D21 |
| Lecture discordante sous surligneur | — | 10 | D11 (`OCR_CRITICAL_ENTITY_DISAGREEMENT`) |

« — » signifie que la raison n’existait pas dans la baseline : ces blocs étaient alors envoyés au modèle ou protégés à tort. Aucun de ces caractères n’est compté comme traduit.

## 4. Budget Interim 32K (passage final)

| Doc | Requêtes | Tokens prompt | Tokens complétion | Max réservé / requête | Max consommé / requête | > 32 768 (réservé) | > 32 768 (usage) | Violations | SHA original inchangé |
|---|---|---|---|---|---|---|---|---|---|
| DOC-001 | 2 | 1 419 | 827 | 19 390 | 1 709 | 0 | 0 | 0 | oui |
| DOC-002 | 2 | 1 380 | 835 | 19 132 | 1 840 | 0 | 0 | 0 | oui |
| DOC-003 | 2 | 967 | 219 | 17 484 | 671 | 0 | 0 | 0 | oui |
| DOC-004 | 13 | 7 907 | 4 508 | 18 538 | 1 402 | 0 | 0 | 0 | oui |
| DOC-005 | 2 | 1 529 | 976 | 19 169 | 1 805 | 0 | 0 | 0 | oui |
| DOC-006 | 27 | 19 442 | 13 865 | 20 988 | 2 498 | 0 | 0 | 0 | oui |
| DOC-007 | 11 | 8 602 | 5 342 | 20 867 | 2 108 | 0 | 0 | 0 | oui |
| DOC-008 | 4 | 2 913 | 1 880 | 19 193 | 1 948 | 0 | 0 | 0 | oui |
| **Total** | **63** | 44 159 | 28 452 | **20 988** | **2 498** | **0** | **0** | **0** | 8/8 |

- **Réservé** : entrée complète réelle (tokenizer o200k, avec cadrage) + sortie maximale (8 000) + marge (2 768). Le garde du moteur refuse tout appel dont le réservé dépasse 32 768.
- **Consommé** : usage renvoyé par le fournisseur (prompt + complétion, raisonnement inclus).
- **Défaut D10 corrigé.** Avant correctif, les métadonnées de rendu étaient comptées dans le budget alors qu’elles ne sont pas envoyées. Un document était ainsi faussement mesuré à 38 522 tokens et bloqué. Il en mesure maintenant 2 676 en réel. Un vrai dépassement reste bloquant (`test_context_wire_budget.py`).
- **Confidentialité.** Les requêtes ne portent que sur les 8 SHA admis par l’autorisation propriétaire, conservée hors Git et expirable. Aucun autre document n’est envoyé.
- **Comparaison avec la baseline.** 43 requêtes, max réservé 22 274, max consommé 3 595 : la baseline respectait déjà la borne.
  - Le final compte 25 reprises uniques (D8, 83 blocs relancés). Chaque reprise passe par le même constructeur de contexte et le même garde, et coûte au moins une requête.
  - Le premier passage compte donc au plus 38 requêtes, contre 43 en baseline. Moins de blocs sont envoyés, du fait des gardes D6, D9, D11, D13, D21 et D25.

## 5. Ce que ces chiffres ne prouvent pas

- **La justesse des traductions.** Aucune référence humaine n’est disponible, `translation_score` vaut `NULL` et Qwen privé est `NOT_AVAILABLE`.
- **La justesse de la détection de langue sur les fragments courts.** Sur DOC-003 et DOC-005, des faux positifs sont documentés (limites 7 et 14).
- **La stabilité d’un passage à l’autre.** Le modèle n’est pas déterministe : les compteurs de rendu varient entre passages faits sur la même analyse (limite 15).
