# Réécriture de l'historique du 28/10/2026

## Objet

Le fournisseur LLM temporaire compatible OpenAI, utilisé en attendant le moteur de traduction privé, porte
désormais le nom **Interim** dans tout le dépôt et sur **tout l'historique** : identifiants Python et TypeScript,
noms de fichiers (`backend/app/ai/translation/interim.py`, `interim_guard.py`, `tools/interim_owner_corpus_run.py`,
`tools/interim_synthetic_acceptance.py`, tests `test_interim_*.py`, `frontend/src/public/interim-routes.json`,
`reports/prompt-1/INTERIM-TRANSITION.md`), variables d'environnement (`TRANSLATOR_INTERIM_*`), codes d'erreur
(`INTERIM_*`), clés des exports anonymisés, rapports, messages de commit et nom de branche
(`feature/interim-owner-authorized-corpus-20261008`). Les mots « manuscrit / manuscrite » ne sont pas concernés.

Rien d'autre n'a changé :

- chaque fichier de chaque commit redevient **octet pour octet** l'original quand on applique le renommage inverse
  (vérification exhaustive : dépôt de travail : 31 commits, 587 paires de fichiers, 0 écart ; dépôt public : 11 commits, 500 paires, 0 écart) ; seule exception, deux fichiers de test (`backend/tests/unit/test_form_structure_guard_final.py`, `backend/tests/unit/test_source_ink_guard_final.py`) dont une ligne d'import a été replacée à son rang alphabétique, le nouveau nom ne se triant pas au même endroit : permutation pure de lignes, validée par `ruff check --select I` (sans ce tri, l'étape lint de la CI échouait sur 7 branches) ;
- auteur, committer et dates de chaque commit sont conservés à l'identique (Hamza NORDINE) ; même structure de
  parents et de branches ;
- formules, poids et seuils du score sont inchangés.

## Équivalence vérifiée

| Contrôle | Résultat |
|---|---|
| Tests backend, 11 branches, commande CI exacte (`ruff check backend tools` + pytest unit/integration/e2e/regression/security) | arbre d'origine et arbre renommé identiques test par test : 549, 418, 360, 294, 226, 591, 610, 659, 719, 802, 873 tests réussis selon la branche, 0 échec |
| Après le tri des imports | `ruff check backend tools` : 0 erreur sur les 24 têtes (12 branches × 2 dépôts) ; pytest relancé sur les 7 branches concernées et sur `main` et RUN29 publics : identiques test par test à l'original |
| Score figé (rejeu de la chaîne de mesure RUN29) | code d'origine sur résultats d'origine contre code renommé sur résultats renommés : 0 écart sur 34 865 champs (mesures, fiches v1 et v2, vérifications arithmétiques) ; 0 écart avec les résultats historiques |
| Frontend RUN29 (`npm ci`, typecheck, tests, build) | identique avant et après : typecheck OK, 30 tests réussis sur 30 (8 fichiers), build OK |
| Identités | auteur et committer Hamza NORDINE sur les 31 + 11 commits réécrits, dates conservées, aucune signature à retirer |
| Assainissement du dépôt public | même écart public/privé sur les 12 branches avant et après renommage |
| Audits de dépendances du 28/10/2026 | `npm audit --audit-level=high` : 6 vulnérabilités hautes (vite, launch-editor, zod) ; `pip-audit --strict` : 39 sur Pillow 12.3.0 (corrigé en 13.0.0). Résultat identique sur l'arbre d'origine : avis publiés après l'audit RUN29 du 16/10 (alors sans vulnérabilité), sans lien avec le renommage ; correction à traiter séparément, la montée de Pillow pouvant modifier le rendu |

## Lire les rapports antérieurs au 28/10/2026

1. **SHA.** Les messages de commit, rapports, demandes de fusion et commentaires antérieurs citent les SHA de l'historique d'avant
   réécriture (commits et exécutions CI). Ces exécutions CI ont porté sur ces anciens commits ; la table en fin de
   document donne le commit correspondant de l'historique actuel (même contenu au renommage près).
2. **Empreintes.** Les empreintes citées ont été calculées sur les octets d'avant renommage. Valeurs avant et
   après renommage :

| Empreinte | Avant renommage | Après renommage |
|---|---|---|
| Code RUN29 (`backend/app` + `tools`) | `3846f2296a271396` | `88bf462d7f53a6ff` |
| Tests RUN29 (`backend/tests`) | `efadfa6a14d7a9f9` | `fb2c4adfc464960f` |
| Règle de mesure RUN29 | `4d6b306029f8745b` | `b0b0261eaabecda8` |
| Règle de mesure, tête de la branche RUN28 | `b827d913b8a71d88` | `78b32b37a08b2727` |

   Gels de méthode : dans les gels v1 (4 fichiers) et v2 (8 fichiers), seuls `tools/recette/scorecard.py` et `tools/recette/measure_v2.py` changent, uniquement par le nom des fichiers de résultat qu'ils lisent ; nouvelles sommes SHA-256 : `scorecard.py` `560959c506d563b3a57cbfa5e69dd110b234cfce02cce1e2792db9c141ec5a7b`, `measure_v2.py` `ff1929717bd2743273833767999b059c846cd3505495ec56f7602ada40e8bb29`. La règle RUN28 `08e998169c0dad9b` citée dans les rapports RUN28 et RUN29 a été calculée sur un état de travail local antérieur à l'expurgation des fragments hérités, jamais publié : elle ne correspond à aucun commit des dépôts et n'est pas touchée par le renommage.

3. **Configuration.** Toute configuration existante doit utiliser les nouveaux noms : variables
   `TRANSLATOR_INTERIM_*` (l'ancien préfixe n'est plus lu), route frontend `/interim-routes.json`. Les fichiers de
   résultat produits avant le renommage portent l'ancien préfixe ; ils doivent être renommés `interim-run-summary.json`
   et `interim-service-result.json` (et leur contenu renommé de la même façon) avant tout nouveau calcul de score.
   C'est exactement ce qu'a fait le rejeu ci-dessus, qui retrouve le score historique à l'identique.

## Correspondance des branches (dépôt de travail)

| Branche | Ancienne tête | Nouvelle tête |
|---|---|---|
| `feature/industrialisation-finale-20261009` | `f44ebb8` | `dd1ba25` |
| `feature/interim-owner-authorized-corpus-20261008` | `60bd172` | `40ecb55` |
| `feature/prompt-1-industrialisation-20261008` | `0016589` | `bb14c87` |
| `feature/prompt-2-fidelite-20261008` | `154691d` | `08cebd0` |
| `feature/run18-regressions-20261011` | `026b0f9` | `0069f52` |
| `feature/run25-recette-finale-20261012` | `e006b6d` | `6ae77ed` |
| `feature/run26-score-confiance-20261012` | `c0a0629` | `84e449d` |
| `feature/run27-score-remediation-20261013` | `54bf5f2` | `5cd2507` |
| `feature/run28-moteur-simplification-20261014` | `0198654` | `b3855b0` |
| `feature/run29-correction-bout-en-bout-20261016` | `11b424d` | `f4c5f4f` |
| `integration/prompt-1-2-20261008` | `d28a636` | `35c40d7` |
| `main` | `d28a636` | `35c40d7` |

## Correspondance des commits (dépôt de travail, ordre chronologique)

| Date | Ancien SHA | Nouveau SHA | Sujet |
|---|---|---|---|
| 2026-10-07 | `3c21bc2` | `5bb138b` | feat: plateforme documentaire privée et framework QA |
| 2026-10-07 | `c604cd4` | `32cc650` | feat: industrialiser la plateforme privée, les preuves qualité et les contrôles de product |
| 2026-10-07 | `6fb913a` | `3367d2f` | fix: borner la détection raster et livrer le bilan industriel vérifié |
| 2026-10-08 | `69be130` | `ee72b38` | feat: industrialiser preprocessing local, contexte privé 32K et previews versionnées |
| 2026-10-08 | `b7e40a0` | `ce6db30` | feat: provider Interim synthétique explicite et contrat total 32K |
| 2026-10-08 | `0016589` | `bb14c87` | docs: preuves finales prompt 1 et signal d'exécution completed |
| 2026-10-08 | `154691d` | `08cebd0` | Implémenter et mesurer le moteur de fidélité DOCX/PDF avec revue explicite |
| 2026-10-08 | `d28a636` | `35c40d7` | merge: intégrer prompt 1 (industrialisation) et prompt 2 (fidélité) |
| 2026-10-08 | `60bd172` | `40ecb55` | feat(interim): run authorised originals through Interim within the 32K budget |
| 2026-10-09 | `ebb09eb` | `182a9a7` | Industrialisation finale : correctifs D1-D27, recette des 8 PDF et rapports avant/apres |
| 2026-10-09 | `f44ebb8` | `dd1ba25` | Rapports finaux : resultat CI du SHA ebb09eb (rapports uniquement) |
| 2026-10-11 | `e3714b6` | `63137ec` | run18 : correctifs F1-F19 des regressions run17, statut par bloc et mesure independante |
| 2026-10-11 | `1069303` | `ff07207` | run18 : rapports de recette (causes racines, regressions, fidelite, couverture, tests, lim |
| 2026-10-11 | `026b0f9` | `0069f52` | run18 : resultat CI du SHA 1069303 dans les rapports (rapports uniquement) |
| 2026-10-12 | `de0af16` | `c20f798` | run25: fix scan reconstruction root causes F20-F24 |
| 2026-10-12 | `c14197d` | `578459b` | run25: recette reports and anonymised metrics (8 documents REVIEW_REQUIRED) |
| 2026-10-12 | `e006b6d` | `6ae77ed` | run25: record GitHub CI result on c14197d in reports |
| 2026-10-12 | `83e7d9e` | `e4d108c` | RUN26: preuves de génération (P0), score de confiance documentaire, F25-F28 |
| 2026-10-12 | `b61f25a` | `5899360` | RUN26: rapports et exports anonymisés — seuil 94 non atteint, REVIEW_REQUIRED x8 |
| 2026-10-13 | `c0a0629` | `84e449d` | RUN26: résultat réel de la CI du commit b61f25a (success ; portes privées skipped) |
| 2026-10-13 | `a3035c6` | `1e72d0e` | RUN27: score v2 vérifiable, empreinte de règle, pack humain et correctifs F29-F34 |
| 2026-10-13 | `c1003b7` | `9470ad6` | RUN27: rapports et exports anonymisés (seuil 94 non atteint, REVIEW_REQUIRED x8) |
| 2026-10-13 | `54bf5f2` | `5cd2507` | RUN27: résultat réel de la CI du commit c1003b7 (success ; portes privées skipped) |
| 2026-10-14 | `d189972` | `5cc47e7` | RUN28: causes racines F35-F42, parcours natif XLSX/PPTX, synthèse de contrôle |
| 2026-10-14 | `c973e73` | `b4f0bf7` | Confidentialité : expurgation de fragments documentaires hérités (tête de branche) |
| 2026-10-14 | `cb32d76` | `1dcb0af` | RUN28 : rapports et exports anonymisés (seuil 94 non atteint, 8 × REVIEW_REQUIRED) |
| 2026-10-14 | `a4a86eb` | `bef6286` | RUN28 : résultat réel de la CI sur cb32d76 (succès, décomptes lus dans les journaux) |
| 2026-10-16 | `0198654` | `b3855b0` | docs: guide de déploiement détaillé (Compose validé, Helm, production) |
| 2026-10-16 | `54b9bbb` | `7b2104d` | RUN29 : corrections de rendu, d'OCR et du moteur privé (F43-F53) |
| 2026-10-17 | `30de55f` | `01fa3c3` | RUN29 : rapports, exports anonymisés et verdict NO-GO |
| 2026-10-17 | `11b424d` | `f4c5f4f` | RUN29 : résultat CI du commit des rapports |

Le dépôt public `compleoRepos/atelier-documentaire` a été recréé le 28/10/2026 à partir des mêmes instantanés
assainis, renommés de la même façon ; ses messages de commit citent les nouveaux SHA ci-dessus.
