# RUN27 — Pack de validation humaine

> **État : NOT_STARTED sur les 8 documents — 0 ligne revue sur 1 072, 0 relecteur autorisé.** Aucune validation n’a été simulée. Les quatre sous-composantes humaines de chaque document restent **inconnues** (`HUMAN_REFERENCE_MISSING`) : elles valent 0 dans le score officiel. C’est la raison structurelle pour laquelle aucun document ne peut dépasser son plafond (76,8, ou 68,5 pour DOC-003), donc 94.

## 1. Ce que le score ne peut pas mesurer seul

| Sous-composante | Dimension | Ce qu’un humain doit fournir |
| --- | --- | --- |
| `ocr.character_accuracy` | OCR | transcription de référence des zones scannées (ou décision « exact », « corrigé », « illisible ») |
| `translation.semantic_accuracy` | Traduction | traduction de référence validée, ou décision ACCEPT / MINOR / MAJOR / REJECT sur la cible produite |
| `entities.names_clauses_verified` | Entités | contrôle des noms, montants, dates, identifiants, clauses et unités (OK / KO / sans entité) |
| `hallucination.proven_by_reference` | Hallucination | contrôle ajout / omission (NONE / ADDITION / OMISSION / BOTH) |

## 2. Outil (`tools/recette/human_validation.py`, version `human-validation-1`)

| Commande | Rôle |
| --- | --- |
| `export --ref LABEL=RUN_DIR [--compare LABEL=RUN_DIR] --out PACK_DIR` | un tableur CSV par document (UTF-8 avec BOM, séparateur « ; ») + `manifest.json` (identifiant de ligne et empreinte SHA-256 du texte source de chaque ligne) + modèles vides `reviewers.json` et `signoff.json` |
| `ingest --pack PACK_DIR --out REVIEW.json` | contrôle et agrège les décisions ; produit les sous-composantes par intervalles pour `scorecard_v2.py --review` et un journal privé des divergences |
| `status --pack PACK_DIR` | avancement par document (comptes uniquement) |

Toute sortie est refusée si elle se trouve dans le dépôt : le pack contient le texte des documents et reste dans l’espace privé autorisé.

## 3. Format d’une ligne

Colonnes fournies : identifiant de ligne, document, page, bloc, boîte, page scannée, confiance OCR, statut produit et alertes du run de référence, besoin de contrôle d’entités, besoin de traduction, texte source, cible du run de référence et du run comparé.

Colonnes à remplir : `ocr_decision`, `reference_transcription`, `reference_translation`, `translation_decision_<run>`, `hallucination_<run>`, `entities_<run>`, `reviewer_id`, `reviewed_at`, `comment`.

## 4. Règles d’ingestion (contrôlées par tests)

- Un relecteur doit être déclaré dans `reviewers.json` avec une date d’autorisation ; une décision antérieure à l’autorisation est refusée.
- Ligne inconnue, texte source modifié (empreinte différente du manifeste), décision hors vocabulaire, date manquante : refus.
- Les blocs `NOT_TRANSLATABLE` ne demandent pas de décision de traduction.
- Le document n’est `VALIDATED` côté humain que si **toutes** ses lignes requises sont revues et si `signoff.json` porte la signature d’un relecteur autorisé.

## 5. Calcul sur la seule partie validée (intervalles)

Pour une sous-composante, avec une part validée *s* des caractères concernés et une exactitude *a* mesurée sur cette partie : **basse = s · a**, **haute = s · a + (1 − s)**. Avec *s = 0*, la sous-composante reste inconnue ; elle n’est jamais mise à une valeur positive par défaut. Exemple : exactitude 0,98 sur 40 % du contenu → [0,392 ; 0,992].

Tests : `backend/tests/unit/test_human_validation.py` (6 tests synthétiques : export privé et sans relecteur, pack vide = inconnues, relecteur non autorisé ou source modifiée refusés, revue antérieure à l’autorisation ou décision inconnue refusée, validation partielle = intervalles honnêtes sans validation du document, revue complète signée = validation et divergences calculées).

## 6. Pack exporté pour RUN27 (espace privé)

Référence : run27b ; comparaison : run26b. Le pack existe, avec manifeste et modèles vides. `status` et `ingest` ont été exécutés sur le pack vide pour prouver qu’il ne produit aucune validation.

| Document | Lignes à revoir | Lignes revues | État |
| --- | --- | --- | --- |
| DOC-001 | 47 | 0 | NOT_STARTED |
| DOC-002 | 24 | 0 | NOT_STARTED |
| DOC-003 | 13 | 0 | NOT_STARTED |
| DOC-004 | 229 | 0 | NOT_STARTED |
| DOC-005 | 89 | 0 | NOT_STARTED |
| DOC-006 | 418 | 0 | NOT_STARTED |
| DOC-007 | 178 | 0 | NOT_STARTED |
| DOC-008 | 74 | 0 | NOT_STARTED |
| **Corpus** | 1072 | 0 | NOT_STARTED |

## 7. Protocole proposé (à exécuter par des relecteurs autorisés)

1. Désigner au moins un relecteur bilingue par langue source (arabe, espagnol, italien, néerlandais, norvégien, finnois, anglais) ; l’inscrire dans `reviewers.json` avec sa date d’autorisation.
2. Revoir en priorité les lignes à alerte critique ou d’erreur, puis les identifiants et montants (colonne « besoin de contrôle d’entités »), en comparant toujours à **l’image de l’original**, pas à l’OCR (leçon de MV-01).
3. Remplir les décisions ; une transcription de référence est attendue pour toute ligne OCR corrigée.
4. Exécuter `ingest`, puis `scorecard_v2.py --review REVIEW.json` : seules les parties validées entrent dans le score, par intervalles.
5. Signer `signoff.json` uniquement quand toutes les lignes requises d’un document sont revues.
6. Archiver le pack, le journal des divergences et le score recalculé dans l’espace privé.

## 8. Preuves manquantes, par dimension

| Dimension | Preuve manquante | Effet actuel |
| --- | --- | --- |
| Traduction | références de traduction validées | moitié de la dimension inconnue (entière pour DOC-003) |
| Entités | contrôle humain des noms, clauses et unités | un tiers de la dimension inconnu |
| OCR | transcriptions de référence | moitié de la dimension inconnue |
| Hallucination | contrôle ajout / omission | un tiers de la dimension inconnu |
