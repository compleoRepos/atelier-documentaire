# DICE (RAG) — protocole d'annotation humaine

Les mesures automatiques du LOT 2 (termes attendus, nombres, identifiants,
chrF contre une référence candidate) **ne mesurent pas la fidélité
sémantique**. Elles ne remplacent ni ce protocole ni la relecture humaine de
chaque document livré, qui reste obligatoire quel que soit le score.

Statut au LOT 2 : **aucun annotateur n'a été mobilisé** ; la fidélité est
donc NON MESURÉE. Ce protocole et le paquet généré sont prêts à l'emploi.

## 1. Annotateurs

* par paire de langues : au moins **deux** traducteurs professionnels dont la
  langue cible est la langue maternelle, plus un relecteur du domaine (RH,
  paie, banque, juridique, administratif) pour l'arbitrage ;
* aucun annotateur ne connaît la variante (A sans RAG, C avec RAG) d'une
  traduction ;
* les annotateurs n'ont pas accès aux références candidates synthétiques
  (elles ont été rédigées par l'outil et ne sont pas des références humaines).

## 2. Paquet (aveugle)

`tools/rag_lot2_eval.py --annotation-pack <dossier hors dépôt>` écrit :

* `pack.csv` : une ligne par bloc et par traduction, avec un identifiant
  aléatoire de traduction (`X` ou `Y`, tiré par document) ;
* `key.json` : la correspondance `X/Y → A/C`, **à remettre uniquement au
  responsable de l'analyse**, jamais aux annotateurs.

Le paquet contient des textes : il reste hors dépôt et n'est transmis que par un
canal approuvé.

## 3. Grille par bloc (inspirée de MQM)

| Colonne | Valeurs |
|---|---|
| `terminology` | `ok`, `wrong_term`, `inconsistent`, `glossary_violation` |
| `accuracy` | `ok`, `mistranslation`, `omission`, `addition`, `untranslated` |
| `numbers_dates_ids` | `ok`, `changed`, `missing`, `format_only` |
| `fluency` | `ok`, `grammar`, `spelling`, `unnatural` |
| `register` | `ok`, `inadequate` (registre administratif, juridique) |
| `severity` | `none`, `minor`, `major`, `critical` (une erreur `critical` rend le document inutilisable sans correction) |
| `comment` | texte libre, sans donnée personnelle |

Par document : `deliverable_after_review` (`yes`/`no`) et préférence
`X`, `Y` ou `equal`.

## 4. Analyse

* accord inter-annotateurs : alpha de Krippendorff par colonne (seuil
  d'interprétation fixé avant l'analyse, par exemple 0,67) ; les désaccords sont
  arbitrés par le relecteur du domaine ;
* résultats par paire de langues et par catégorie de document, avec effectifs ;
  aucune conclusion sur une paire ou une catégorie sous dix blocs annotés ;
* décision : un gain de C ne peut être affirmé que si les erreurs `major` et
  `critical` diminuent sans hausse ailleurs, sur des documents représentatifs
  des documents réels (le corpus du LOT 2 est synthétique).

## 5. Confidentialité

Les documents réels, s'ils sont annotés plus tard, restent dans
l'environnement privé ; seuls des agrégats (compteurs, alphas, taux) peuvent
être publiés.
