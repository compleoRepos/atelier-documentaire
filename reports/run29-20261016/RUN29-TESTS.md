# RUN29 — Tests exécutés, commandes et résultats

> Un test réussi **ne prouve pas** qu'un document est professionnellement acceptable. Les tests automatisés de ce rapport vérifient des comportements du code ; ils ne remplacent ni la validation humaine (0/1 072 ligne revue) ni l'inspection des fichiers générés.

## 1. Empreintes de l'arbre testé

Toutes les exécutions finales de ce rapport portent sur le **même arbre de travail**, figé pendant les mesures (aucune modification de code ni de test entre le début et la fin, vérifié par empreinte au début et à la fin de chaque exécution).

| Élément | Empreinte (16 premiers caractères) | Contenu |
|---|---|---|
| Code produit (fermeture mesurée par les lanceurs) | `3846f2296a271396` | code final RUN29, correctifs F43 à F53 |
| Tests | `efadfa6a14d7a9f9` | suite finale, dont les 6 fichiers RUN29 |
| Règle de mesure RUN29 | `4d6b306029f8745b` | 29 fichiers produit + 5 outils de mesure |
| Règle de mesure RUN28 (historique) | `08e998169c0dad9b` | arbre mesuré du RUN28 |
| `backend/requirements.txt` | `25e3daf29a0e82e0` | dépendances auditées |

## 2. Résultats finaux

| Exécution | Commande (depuis la racine du dépôt) | Résultat | Durée | Empreintes début = fin |
|---|---|---|---|---|
| Suite backend « run29c » (commande exacte de la CI) | `PYTHONPATH=backend pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security` | **873 passed, 0 failed, 0 error, 0 skipped**, 75 avertissements | 312,4 s | oui |
| Golden « run29c » : pipeline technique complet sur les **8 originaux confidentiels** (copies locales ignorées par Git), moteur `offline` (aucun modèle invoqué) | `PYTHONPATH=backend pytest backend/tests/golden_dataset` | **8 passed, 0 failed, 0 error, 0 skipped**, 63 avertissements | 1 220 s | oui |
| Analyse statique | `ruff check backend tools` (ruff 0.16.10) | aucune erreur | — | — |
| Format | `ruff format --check` sur les 14 fichiers Python modifiés ou ajoutés | 14 fichiers déjà formatés | — | — |
| Espaces | `git diff --check` | aucune erreur | — | — |
| Audit des dépendances Python | `pip-audit -r backend/requirements.txt --strict` (pip-audit 2.10.1) | « No known vulnerabilities found » | 44 s | — |
| Frontend (non modifié en RUN29) | `npm ci && npm run typecheck && npm test && npm run build && npm audit --audit-level=high` | `npm ci` rc=0 ; typecheck rc=0 ; **30 tests passés (8 fichiers)** ; build rc=0 ; `npm audit` : 0 vulnérabilité | 60 s + 71 s + 1 s | — |
| Intégration continue du commit poussé | workflow `ci.yml` | voir [§ 8](#8-intégration-continue) | — | — |

Répartition des 873 tests : 837 unitaires, 28 d'intégration, 3 de bout en bout, 2 de non-régression du pipeline, 3 de sécurité.

## 3. Tests ajoutés par le RUN29

71 tests dans 6 nouveaux fichiers. Ils utilisent **uniquement des scènes synthétiques** (images et textes inventés) : aucun document, texte ou fragment du corpus privé.

| Fichier | Tests | Correctifs couverts | Ce qui est réellement exécuté | Doubles de test (identifiés) |
|---|---|---|---|---|
| `test_run29_layout_regressions.py` | 14 | F43 (×4), F44 (×5), F45 (×5) | le vrai planificateur de rendu scan (`pdf_fidelity.py`) sur des rasters synthétiques | aucun moteur ; `monkeypatch` uniquement pour les contre-épreuves (désactivation du correctif) |
| `test_run29_render_regressions.py` | 27 | F48, F48b, F49, F50, F50b, F50c | le vrai test de filet, le vrai contrôle `RENDER_RULE_ERASED` (dont 2 tests de bout en bout par `measure_render_fidelity` sur deux rendus d'aperçu réels) et le vrai contrôle des glyphes coupés | `monkeypatch` uniquement pour les contre-épreuves |
| `test_run29_ocr_regressions.py` | 4 | F51 | la vraie règle de prudence OCR (`ocr_recovery.py`) | `monkeypatch` pour la contre-épreuve |
| `test_run29_private_engine.py` | 10 | F46, F47 | un **vrai tokenizer** `transformers` construit en mémoire (pas de téléchargement), donc le vrai type de retour de `apply_chat_template` ; le vrai préflight 32 768 | **transport HTTP factice** (`httpx.MockTransport`) qui refuse tout appel : il prouve que la garde décide **avant** le réseau. Aucune inférence |
| `test_run29_private_chunking.py` | 5 | F52 | la vraie politique de découpage, de plafond (40 blocs) et de redécoupage borné du service de traduction | **moteur privé factice**, identifié comme tel, qui renvoie des réponses scriptées (invalides puis valides). Aucune inférence, aucun réseau |
| `test_run29_rule_crossing.py` | 11 | F53 | le vrai contrôle « texte barré par un filet » sur les lignes que PyMuPDF dessine réellement (page de brouillon) et son câblage dans le planificateur | `monkeypatch` pour la contre-épreuve et pour forcer le résultat du contrôle dans le test de câblage |

Deux tests historiques ont été ajustés (`test_run27_render_regressions.py`, `test_run28_render_regressions.py`) : leurs scènes synthétiques déclenchaient légitimement les nouveaux contrôles F50/F53 ; l'attente vérifiée par ces tests n'est pas assouplie (détail dans [RUN29-IMPLEMENTATION-CHANGES.md](RUN29-IMPLEMENTATION-CHANGES.md)).

### 3.1 Contre-épreuves

Chaque correctif a été vérifié **dans les deux sens** : le test passe avec le correctif et échoue sans lui.

| Correctif | Contre-épreuve | Résultat |
|---|---|---|
| F43–F45 | fichier de tests exécuté contre `pdf_fidelity.py` du RUN28 (copie temporaire) | 9 échecs, 5 réussites ; les 5 réussites sont des abstentions et des non-régressions qui doivent rester vraies. Une partie des échecs vient de constantes absentes du RUN28 : la contre-épreuve comportementale est faite par interrupteur (dégagement 0 ; F44 et F45 désactivés → `LAYOUT_OVERFLOW`) |
| F48 | pontage désactivé (`_RULE_GAP_PX = 0`) | 1 échec attendu : la couverture efface le filet |
| F49 | contrôle neutralisé | 3 échecs attendus |
| F50 / F50b / F50c | interrupteurs `_CUT_GLYPH_CHECK`, `_CUT_GLYPH_RULE_MAX_THICK_PT`, `_CUT_GLYPH_OWN_CHECK` | la couverture coupant les glyphes est acceptée sans le correctif ; un filet est refusé à tort sans F50b |
| F51 | seuil de prudence ramené à 0 | le bloc redevient « lexicalement confirmé » |
| F52 | fichier de tests exécuté contre le service de traduction du RUN28 | 4 échecs sur 5 (le test de profondeur bornée passe des deux côtés, attendu) |
| F53 | interrupteur `_SCAN_CHECK_TEXT_OVER_RULES = False` | le contrôle n'est pas exécuté et le placement barré est accepté |

## 4. Rejeux du corpus DOC-001 à DOC-008 (fichiers réels, privés)

Ces exécutions traitent les 8 originaux autorisés de bout en bout (analyse, OCR, segmentation, traduction, contrôles, rendu PDF, aperçus). Les originaux, sorties et aperçus restent hors du dépôt.

| Exécution | Code | Moteur de traduction | Requêtes envoyées | Résultat |
|---|---|---|---|---|
| `run29a` (baseline) | RUN28 | **mémoire** de traduction (inférences Interim réelles passées, revalidées par les gardes actuelles) | 0 | 8/8 sans erreur ; 0 statut et 0 traduction changés ; 31/31 aperçus identiques au pixel près au RUN28 : la baseline est reproduite |
| `run29h` puis `run29i` | F43–F51 puis F43–F52 | mémoire | 0 | étapes intermédiaires ; `run29i` = `run29h` (0 statut, 0 traduction, 0 aperçu différents) prouve que F52 et l'interrupteur F44 ne changent rien côté Interim |
| **`run29j` (verdict)** | **F43–F53 (`3846f2296a271396`)** | mémoire | **0** | 8/8 sans erreur, 122 s ; originaux inchangés (empreinte vérifiée avant et après) ; seul DOC-004 change par rapport à `run29i` (2 refus F53) ; 7 documents identiques au pixel près |
| `run29oss`, `run29oss2`, `run29oss3` | F43–F47 puis F43–F52 | **gpt-oss-20b local, inférences réelles** | voir [RUN29-ENGINE-COMPARISON.md](RUN29-ENGINE-COMPARISON.md) | comparaison de moteurs, pas un verdict produit |

**Aucune nouvelle inférence Interim** n'a eu lieu en RUN29 : toutes les traductions Interim viennent de la mémoire d'inférences réelles antérieures. Une traduction de mémoire n'est **jamais** comptée comme une nouvelle inférence (`requests_sent = 0`, origine `memory` dans la provenance de chaque bloc).

## 5. Couverture des thèmes demandés

| Thème | Où c'est testé | Nature |
|---|---|---|
| Extraction de texte, segmentation, identification des blocs | `test_segmentation_final`, `test_ocr_*`, `test_preprocessing_*`, `test_documents_pipeline` | unitaire, fichiers synthétiques |
| Protection des entités | `test_entities_multilingual`, `test_entities_v2`, `test_interim_guard`, `test_run28_ordinal_retry` | unitaire |
| Appels réels au moteur | **aucun test automatisé** n'appelle un vrai modèle ; les seuls appels réels de ce RUN sont les passes gpt-oss du corpus (§ 4) | limite assumée (voir § 7) |
| Caches / mémoire de traduction | `test_interim_usage_cache`, `test_run26_traceability`, rejeu `run29a` | unitaire + corpus réel |
| Couverture des blocs, réinjection, reconstruction | `test_pdf_cell_fallback`, `test_scan_render_plan_final`, `test_docx_*`, `test_run28_office`, e2e `test_document_flow`, `test_prompt1_scanned_flow` | unitaire, intégration, bout en bout (moteur `offline`) |
| Tableaux et cellules | `test_private_table_mapping`, `test_form_structure_guard_final`, F48/F49/F53 | unitaire |
| Débordements | F44, F45, `test_cover_growth_final`, `test_line_verification_final` | unitaire |
| Résidus de la source | `test_source_ink_guard_final`, F50/F50c | unitaire |
| Intégrité des éléments protégés | F43, `test_run27_render_regressions` | unitaire |
| Rendu des pages | F49 (bout en bout sur aperçus réels), `test_visual_v2`, `test_prompt1_previews` | unitaire, intégration |
| Erreurs et reprises | F46/F47 (fail-closed), F52 (redécoupage), `test_interim_chunk_split`, `test_interim_unchanged_retry`, `test_tesseract_timeout_retry` | unitaire, transport/moteur factices |
| Comparaison avant/après | `test_baseline_gate`, `tools/recette/*` (mesure gelée), rejeux du corpus | unitaire + mesure réelle |

## 6. Résultats invalidés ou remplacés (à ne pas citer comme finaux)

| Exécution | Résultat | Raison |
|---|---|---|
| Suite « run29a » (code `365d4c7aa94c0e7c`, F43–F51) | 843 passed, 0 failed | valide pour cet arbre antérieur seulement (avant F52 et F53) |
| Golden « run29a » (même code) | 8 passed | idem |
| Suite « run29b » (code `67dffd94acfcab8a`, F43–F52) | 862 passed, 0 failed | valide pour ce code seulement ; remplacée par run29c (F53 ajouté) |
| Golden « run29b » | **arrêté volontairement** à 5/8 | F53 changeait le code pendant l'exécution : résultat incomplet et obsolète |

## 7. Ce que ces tests ne prouvent pas

- **Aucune inférence complète n'est prouvée par un test automatisé** : la suite utilise un transport HTTP et un moteur privé factices (identifiés au § 3) ; le golden traite les 8 vrais originaux mais avec le moteur `offline` (aucun modèle invoqué) : il vérifie le pipeline technique (analyse, OCR, rendu, contrôles, intégrité des originaux), pas la traduction. Les seules inférences réelles du RUN29 sont celles de gpt-oss-20b sur le corpus.
- Les contrôles F49, F50, F50c et F53 ont été calibrés sur des cas étiquetés **du corpus lui-même** ; leur rappel sur d'autres documents n'est pas mesuré.
- La qualité linguistique n'est mesurée par aucun test : 0 référence humaine.

## 8. Intégration continue

Exécution GitHub Actions [38981494304](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/38981494304) sur le commit de code `54b9bbb` (événement `pull_request`, PR brouillon) : **success**.

| Job | Conclusion | Durée |
|---|---|---|
| `frontend` | **success** | 28 s |
| `backend-integration-and-migrations` | **success** | 123 s |
| `backend` | **success** | 202 s |
| `container-and-manifest-validation` | **success** | 123 s |
| `private-acceptance` | skipped | — (non déclenché : exécuteur privé et porte de mise en production manuelle) |
| `manual-release-gate` | skipped | — (non déclenché : exécuteur privé et porte de mise en production manuelle) |

Les deux jobs ignorés sont conçus pour ne s'exécuter que sur l'exécuteur privé de la banque (`workflow_dispatch` avec acceptation privée) ou sur décision manuelle : leur absence n'est **pas** une validation. La CI ne traite aucun original (les originaux ne sont jamais sur GitHub) ; elle vérifie la suite technique, les migrations, le frontend, les images et les manifestes.

CI du commit des rapports `30de55f` : exécution [38990744154](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/38990744154) (événement `pull_request`) : **success** — `backend` 179 s, `frontend` 29 s, `backend-integration-and-migrations` 115 s, `container-and-manifest-validation` 139 s ; `private-acceptance` et `manual-release-gate` ignorés pour la même raison. Le commit suivant (le présent ajout) ne modifie que ce rapport ; sa CI est consignée dans la PR.
