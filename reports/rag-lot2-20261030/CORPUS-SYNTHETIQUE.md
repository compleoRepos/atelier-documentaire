# Corpus synthétique du LOT 2

> **Statut : SYNTHÉTIQUE.** Aucune donnée réelle, aucun document client, aucun
> texte issu d'OCR réel. Les « références candidates » sont rédigées par l'outil
> à partir des gabarits : ce ne sont **pas des références humaines**.

## 1. Reproduction

```bash
python tools/rag_lot2_corpus.py --out-dir <répertoire hors dépôt>
```

Le générateur est déterministe : deux exécutions produisent des fichiers
identiques octet pour octet (test `test_corpus_is_deterministic_complete_and_synthetic`).
Il refuse d'écrire dans le dépôt. Sortie : `docs/` (IR + options de
traduction), `expected/` (attentes par construction), `referential.csv`
(import réel), `manifest.json`.

## 2. Composition

| Catégorie | Domaine du document | Documents | Blocs | Termes attendus | Contrôles numériques |
|---|---|---|---|---|---|
| attestation de travail | HR | 5 | 40 | 35 | 25 |
| contrat de travail | HR | 5 | 35 | 60 | 30 |
| bulletin de paie | PAYROLL | 5 | 35 | 40 | 50 |
| relevé bancaire | BANKING | 5 | 30 | 30 | 45 |
| courrier administratif | ADMINISTRATION | 5 | 30 | 25 | 20 |
| procuration (juridique) | LEGAL | 5 | 30 | 30 | 20 |
| tableau récapitulatif de paie | PAYROLL | 5 | 55 | 20 | 20 |
| document « scanné » (bruit d'OCR simulé) | HR | 5 | 40 | 35 | 25 |
| **Total** | | **40** | **295** | **275** | **235** |

Chaque catégorie existe pour les cinq paires EN→FR, AR→FR, ES→FR, DE→FR et
FR→EN. Les 275 occurrences de termes se répartissent en 261 termes
principaux, 10 synonymes et 4 variantes ; 10 relèvent du glossaire client et
265 du référentiel.

Référentiel : 169 lignes, 32 concepts, domaines HR (45), PAYROLL (40), BANKING
(34), ADMINISTRATION (20), LEGAL (20), NOTARIAL (5), INSURANCE (5). Trois
domaines de la taxonomie proposée (FINANCE, TAX, ACADEMIC) ne sont pas
représentés.

## 3. Pièges construits

| Piège | Construction | Comportement attendu |
|---|---|---|
| synonyme ou variante en source | `gross pay`, `CDI`, `attestation d'emploi`… | terme injecté avec la forme lue |
| bruit d'OCR | accents perdus (FR, ES), `ae/oe/ue` (DE), harakat et tatweel (AR), chiffres arabes-indiens, espaces doublées, `cert1fy` | correspondance pliée non ambiguë |
| ambiguïté | `deposit` → `dépôt` / `caution` ; `dépôt` → `deposit` / `filing` | **aucune** injection, signalement |
| domaine frère | cotisations d'assurance (`INSURANCE`) dans un bulletin `PAYROLL` | **aucune** injection |
| glossaire client | `gross salary` → `rémunération brute` (glossaire) contre `salaire brut` (référentiel) | le glossaire l'emporte, dans A comme dans C |
| nombres | montants, dates, identifiants, IBAN fictif, durées | conservés à l'identique (formats locaux admis) |

## 4. Attentes par construction

Pour chaque document, `expected/<document>.json` donne : les termes attendus
(bloc, clé, forme lue, cible attendue, autorité), les contrôles numériques
(montant, date, identifiant, nombre), les sources ambiguës, le terme du domaine
frère et la référence candidate. La référence candidate emploie toujours le
terme principal validé (ou le terme du glossaire client) ; un test vérifie
qu'une sortie identique à la référence obtient 100 % sur tous les contrôles
objectifs et 0 nombre ajouté.

## 5. Limites

* corpus construit par une seule personne (l'outil) : les tournures sont
  régulières et ne représentent pas la variété des documents réels ;
* synonymes et variantes : 14 occurrences sur 275 seulement, trop peu pour une
  mesure fine de ces mécanismes ;
* le bruit d'OCR est simulé sur du texte, sans image : il ne reproduit pas les
  erreurs de segmentation ni les confusions de caractères d'un vrai OCR ;
* la paire FR→EN n'est pas traduisible par le pipeline actuel, qui produit des
  traductions vers le français : seul le plan RAG (termes trouvés, décisions)
  est mesuré pour cette paire ;
* les mesures sémantiques (fidélité, omissions, ajouts, notions juridiques)
  exigent l'annotation humaine décrite dans
  [ANNOTATION-HUMAINE.md](../../docs/rag/ANNOTATION-HUMAINE.md).
