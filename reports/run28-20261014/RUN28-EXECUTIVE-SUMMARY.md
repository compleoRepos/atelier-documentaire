# RUN28 — Résumé exécutif

> **Verdict : RUN28 techniquement livré, mais pas prêt pour la production bancaire.** Corrections réelles et visibles sur 6 documents. Aucune régression visible connue laissée : la seule trouvée, intermédiaire, a été corrigée avant le verdict. Un bloc de DOC-004 déjà en échec est reclassé « encre résiduelle », ce qui ajoute un défaut mesuré, expliqué. Tests backend, golden et frontend verts (§ 4). Mais **8/8 documents restent `REVIEW_REQUIRED`**, 42 défauts critiques mesurés subsistent sur 6 documents, et **0 ligne sur 1 072** du pack humain n’a été revue. Score officiel v2 du corpus : **65,9 → 65,7** (borne haute 90,3, plafond 75,5). Score historique v1 : 74,6 → 73,9. **Seuil de 94 non atteint.**

## 1. Tableau final (anonymisé)

| Document | Score v2 run27 → run28 [borne haute] | v1 | Défauts critiques (scorecard-2) | Alertes critiques produit | Couverture écrite | Ce qui change à l’image | Référence humaine | Statut |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DOC-001 | 63,1 → **62,7** [86,0] | 72,0 → 71,7 | 3 → 3 | 6 → 6 | 58,8 % → 51,0 % | pied de page de références rendu à l’original | 0/47 | **REVIEW_REQUIRED** |
| DOC-002 | 66,7 → **66,7** [89,9] | 75,4 → 75,4 | 4 → 4 | 8 → 8 | 64,4 % → 64,4 % | aucun (pixel-identique) | 0/24 | **REVIEW_REQUIRED** |
| DOC-003 | 62,7 → **62,7** [94,2] | 71,4 → 71,4 | 0 → 0 | 0 → 0 | 74,1 % → 74,1 % | aucun (pixel-identique, non-régression) | 0/13 | **REVIEW_REQUIRED** |
| DOC-004 | 66,2 → **67,0** [90,2] | 75,3 → 75,8 | 25 → 19 | 47 → 35 | 61,8 % → 64,4 % | lignes traduites (corps condensé), raison sociale et case à l’original ; réserves MV-05/06/07 | 0/229 | **REVIEW_REQUIRED** |
| DOC-005 | 58,3 → **53,0** [79,0] | 67,5 → 59,1 | 0 → 0 | 0 → 0 | 21,3 % → 9,8 % | **identifiant de nouveau intact** (MV-01 corrigé) | 0/89 | **REVIEW_REQUIRED** |
| DOC-006 | 73,4 → **73,5** [96,8] | 81,2 → 81,3 | 7 → 5 | 14 → 10 | 93,7 % → 94,0 % | libellé, ligne de tableau, phrase de dates traduits ; bande grise supprimée | 0/418 | **REVIEW_REQUIRED** |
| DOC-007 | 70,3 → **71,1** [94,4] | 78,7 → 79,2 | 11 → 7 | 21 → 13 | 79,6 % → 82,2 % | 4 titres ou libellés traduits, fond blanc, ligne source résiduelle supprimée | 0/178 | **REVIEW_REQUIRED** |
| DOC-008 | 66,4 → **68,6** [91,9] | 75,2 → 77,0 | 5 → 4 | 10 → 8 | 59,1 % → 68,2 % | pied bilingue sans mots source recopiés | 0/74 | **REVIEW_REQUIRED** |
| **Corpus** | 65,9 → **65,7** [90,3] | 74,6 → 73,9 | **55 → 42** | **106 → 80** | 85,0 % → 86,1 % | 6/8 documents modifiés, 27 zones inspectées | **0/1 072** | **8 × REVIEW_REQUIRED** |

Mêmes huit originaux, inchangés. Règle de mesure identique pour les deux colonnes (RUN27, qui reproduit exactement la valeur publiée ; la règle RUN28 donne la même valeur run28). Borne basse = valeur officielle. Affichage au dixième **prudent** : borne basse arrondie vers le bas, borne haute vers le haut (valeurs exactes dans `documents/`). Une borne haute ≥ 94 n’est **jamais** un seuil atteint.

**Pourquoi le score baisse alors que les sorties s’améliorent** : les deux seules baisses (DOC-001, DOC-005, −0,71 sur le corpus) viennent de F35, qui laisse les lignes de références en pixels d’origine. La portée gelée de la mesure v2 les compte encore comme « à traduire ». Sur DOC-005, elle retire aussi le faux mérite qu’accordait RUN27 à un identifiant devenu faux. Les six autres documents gagnent +0,48. La méthode n’a **pas** été modifiée pour masquer cet effet (RUN28-BEFORE-AFTER § 3).

## 2. Ce qui a été fait

| Catégorie | Contenu |
| --- | --- |
| **(a) Améliorations réellement visibles** (vérifiées à l’œil sur les PDF) | Identifiant de DOC-005 de nouveau intact (MV-01). Lignes de références rendues à l’original (DOC-001, 004, 005). 10 lignes jusque-là en débordement désormais traduites et placées (DOC-004, 006, 007). Ligne source résiduelle supprimée (DOC-007, MV-03). Fonds gris supprimés (DOC-006, 007). Mots source recopiés supprimés (DOC-008). Phrase de dates traduite après une reprise ciblée (DOC-006). |
| **(b) Améliorations uniquement techniques** | Parcours natif XLSX/PPTX (modification du paquet, sans conversion, vérification native). Six indicateurs de contrôle dans l’interface. Mémoire de traduction revalidée avec invalidations tracées. Arrêt du renvoi en boucle d’un bloc rejeté. Provenance par bloc (`NOT_SENT`, `retry_kind`). Extraction des ordinaux. Audit Qwen/vLLM sans modification. |
| **(c) Défauts corrigés** | F35 (lignes de références), F37 (débordements, 28 → 14), F38/F38b (filets, fonds), F39 (traductions partielles), F40 (cible égale à la source à des marques bidi près ; régression intermédiaire MV-04), F41 (renvoi indéfini), F42 (faux positifs d’entités ordinales). Détails : RUN28-ROOT-CAUSES. |
| **(d) Défauts encore présents** | 42 défauts critiques mesurés et 80 alertes critiques. 14 débordements. Triplet de rendu manquant sur 6 documents et 6 régions protégées modifiées (DOC-004), non analysés en RUN28. Phrases de droite à gauche traduites ligne à ligne (MV-06, critique, invisible pour les métriques). Corps très petits (MV-05). OCR bruité (MV-07). Rognage XLSX non détecté. Qwen non qualifié. Détails : RUN28-OPEN-ISSUES. |
| **(e) Nécessite une validation humaine** | 1 072 lignes du pack (0 revue). Lisibilité de 9 blocs condensés. Sens des lignes de DOC-004 concernées par MV-06 et MV-07. Acceptation métier des lignes de références laissées dans leur langue d’origine. |

## 3. Confidentialité et moteur

- 6 requêtes Interim au total sur la séquence RUN28, toutes sous autorisation privée SHA-listée et expirante, avec garde de 32 768 tokens : 0 violation, réservation max. 16 608. Le verdict run28e ne fait **aucune** requête (mémoire revalidée).
- Originaux, OCR, PDF, planches, pack humain, autorisation et journaux restent dans l’espace privé, hors Git. Ce dépôt ne contient que du code, des tests synthétiques et des exports anonymisés (`documents/`).
- **Audit de confidentialité étendu à tout le dépôt.** Le scanner hérité ne voyait pas les lignes ajoutées aux fichiers déjà suivis : sortie `git diff` colorée. Une fois ce défaut corrigé, l’audit a trouvé deux exemples de codes postaux réels dans un commentaire RUN28, retirés avant tout push. Il a aussi trouvé des **fragments documentaires hérités des runs précédents, déjà poussés** : intitulés, clauses, un code postal, un montant, une date, des fragments d’identifiant, dans des tests, des commentaires et deux rapports. La tête de branche est expurgée (`c973e73`, code AST-identique). **L’historique distant ne l’est pas** : sa réécriture est destructive et attend une décision (RUN28-OPEN-ISSUES, OI-16).
- Qwen/vLLM : intégration prête (fournisseur interchangeable, endpoint privé, garde 32K, aucun repli public), mais **non exécutée contre un vrai serveur**. Elle n’est pas présentée comme opérationnelle.

## 4. Références

- Tests sur l’arbre final exact (code `914d925722133d4d`, AST-identique au code du corpus `25dbea622c921535` ; empreintes identiques au début et à la fin) : backend **802 passed / 0 failed** ; golden **8 passed / 0 failed** ; Angular **30 passed**, typecheck et build OK ; `ruff check` OK ; `npm audit` et `pip-audit` sans vulnérabilité. Détails et résultats invalidés : RUN28-REGRESSION-RESULTS.
- Commits : `d189972` (code et tests), `c973e73` (expurgation héritée), `cb32d76` (rapports). Auteur et committer Hamza NORDINE. Pull request n° 6 en brouillon, empilée sur la branche RUN27, sans fusion. **CI sur `cb32d76` : succès** (backend 802 passed, intégration PostgreSQL et Alembic 28 passed, Angular 30 passed, images Docker et Helm validés ; portes privée et manuelle ignorées par conception). Détails : RUN28-REGRESSION-RESULTS § 8.
