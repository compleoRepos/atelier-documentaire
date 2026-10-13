# RUN27 — Résultats de non-régression

Toutes les exécutions sont liées à une **empreinte de code** (SHA-256 tronqué à 16 caractères de l’ensemble des fichiers Python de `backend/app` et `tools`) et, pour les suites, à une empreinte des tests, relevées **au début et à la fin**. Journaux, JUnit et empreintes complètes sont dans l’espace privé.

## 1. Empreintes

| Élément | Empreinte | Remarque |
| --- | --- | --- |
| Base RUN26 (HEAD de départ) | commit `c0a0629` | règle de mesure RUN26 `311f7804c8b6ce76` |
| Code du corpus verdict run27b | `5204f2d466bf1d0e` | identique au début et à la fin du run |
| Code final (arbre committé) | `62c33087cee540c9` | = `5204f2d466bf1d0e` + `tools/recette/ruler_fingerprint.py`, outil de mesure non importé par le produit |
| Code final hors `ruler_fingerprint.py` | `5204f2d466bf1d0e` | **preuve que le code produit et le lanceur du corpus verdict sont inchangés** |
| Règle de mesure RUN27 | `c6f0bb9a7b180eb6` | 8 fichiers produit diffèrent de la règle RUN26 |
| Méthode v2 gelée | 8 fichiers SHA-256, gelés le 2026-10-13 à 08:11:36Z | vérifiés avant chaque mesure ; gel v1 RUN26 (4 fichiers) intact |

## 2. Corpus des huit originaux

| Run | Durée | Groupes | Empreinte début = fin | Originaux | Requêtes Interim | Réservation max | Violations budget |
| --- | --- | --- | --- | --- | --- | --- | --- |
| run27 (intermédiaire) | 101 s | 3/3 rc = 0 | `1fe412cf86467b02` | SHA-256 inchangés ×8 | 4 (DOC-002 1, DOC-005 2 dont une relance « traduction inchangée », DOC-006 1) | 16 593 ≤ 32 768 | 0 |
| **run27b (verdict)** | 97 s | 3/3 rc = 0 | `5204f2d466bf1d0e` | SHA-256 inchangés ×8 | 1 (DOC-006) | 16 295 ≤ 32 768 | 0 |

- run27 a révélé l’ordinal invalide (F34) ; run27b rejoue la mémoire de run27, revalidée par la garde courante (`invalidated_by_current_guard`).
- 7 documents en `TRANSLATION_MEMORY_REUSE_ONLY` (`model_invoked = False`), DOC-006 en `MIXED_MEMORY_AND_NEW_GENERATION`. Provenance par bloc, traces de requêtes rapprochées, journal horodaté : présents pour les 8 documents (porte de preuves v2 franchie ×8).
- Statut des 8 documents : `REVIEW_REQUIRED`.

## 3. Mesures

| Étape | Résultat |
| --- | --- |
| `measure_run27.sh` (gels v1/v2, registre, planches 6 runs, v2.1, scorecard-1, scorecard-2, vérifications) | rc = 0, 284 s |
| Vérification indépendante v2 | écart ≤ 1,4·10⁻¹⁴ |
| Mesure à règle RUN26 pure (worktree `c0a0629` + fichiers v2 gelés) | v1 publiée RUN26 reproduite ; historique v2 reproduit à 0,0 |
| Rejeu de `scorecard-1` sur les artefacts RUN26 | JSON identique au scorecard final RUN26 |

## 4. Suites de tests

| Suite | Code | Résultat |
| --- | --- | --- |
| Backend au périmètre CI exact (unit, integration, e2e, regression, security), **arbre définitif** (après correctif anti-fuite des tests) | `62c33087cee540c9` début = fin ; tests `b76c7cd037b2c196` début = fin | **719 passed, 0 failed, 0 skipped** (205,28 s) |
| Même suite, arbre avant correctif anti-fuite (4 littéraux de tests modifiés depuis) | `62c33087cee540c9` ; tests `4576ec716b4db311` | 719 passed, 0 failed (210,57 s) |
| Tests ciblés RUN27 (score v2 17, score v1 9, validation humaine 6, régressions F29/E/F34 19, rendu F30–F33 15, empreinte de règle 3) | arbre final ; fichier F29 C/D rejoué après correctif anti-fuite : 19 passed | **69 passed** |
| Golden (8 cas), run de la chaîne RUN27 | début `5204f2d466bf1d0e` | 8 passed, 0 failed (1 205 s) ; l’outil `ruler_fingerprint.py` a été ajouté pendant l’exécution (fin `62c33087cee540c9`) |
| Golden (8 cas), arbre final | `62c33087cee540c9` début = fin (dossier golden inchangé depuis `c0a0629`) | **8 passed, 0 failed, 0 skipped** (1 167,49 s) |
| Frontend Angular (typecheck, tests, build) | frontend inchangé depuis `c0a0629` | typecheck rc = 0 ; **16 passed** ; build rc = 0 |
| `ruff check backend tools` (commande CI) | arbre final | rc = 0 |
| `ruff format --check` sur les fichiers modifiés ou ajoutés par RUN27 | arbre final | rc = 0 |
| `npm audit --audit-level=high` | — | 0 vulnérabilité |
| `pip-audit -r backend/requirements.txt --strict` | — | aucune vulnérabilité connue |

Échecs rencontrés et traités pendant RUN27 :

- Première suite RUN27 (code `5204f2d466bf1d0e`) : **3 échecs sur 716**. Deux doublures de test produisaient une « traduction » contenant le chiffre de l’identifiant du bloc : la garde symétrique F29 les refuse **à juste titre**. Une attente de télémétrie ne connaissait pas la nouvelle clé `invalidated_by_current_guard`. Correction **des tests uniquement** (identifiant épelé, clé attendue) ; code inchangé ; suite relancée : 716 passed, puis 719 sur l’arbre final.

## 5. Contre-épreuves par mutation

| Ensemble | Mutations | Détectées |
| --- | --- | --- |
| Moteur de score v2 (arrondi, porte de preuves, inconnue positive, document absent, défaut critique ignoré) | 5 | 5/5 |
| Rendu F30–F33 (ordre de réduction, pièces, garde couleur, garde de propriété, somme dans les métriques, F33, somme dans le scorer) | 7 | 7/7 |
| Ordinal F34 (règle neutralisée) | 1 | 1/1 (2 échecs) |
| Validation humaine | — | cas négatifs couverts par 6 tests (relecteur non autorisé, source modifiée, décision inconnue, revue antérieure) |

## 6. Contrôle des PDF

- Comparaison pixel par pixel run26b → run27b : DOC-001 et DOC-003 **identiques** ; DOC-008 : 6 octets, aucun changement visible ; 9 pages modifiées sur 6 documents, toutes revues zone par zone sur planches privées (16 zones).
- Rejeux de rendu hors modèle (8 documents, même entrée) pour chaque correctif de rendu ; une régression F31 (tampon effacé) a été trouvée sur planche et corrigée avant le corpus.

## 7. Confidentialité

- Aucun original, OCR, IR, PDF, image, planche, texte de document, nom de fichier ou empreinte réelle d’original, ni l’autorisation, n’est versionné. Les exports `documents/*.json` ne contiennent que des identifiants `DOC-00x`, des identifiants de blocs, des compteurs, des ratios et des codes.
- Analyse anti-fuite avant commit (mots distinctifs, 4-grammes et nombres du corpus comparés aux ajouts Git ; préfixes d’empreintes et noms numériques des originaux ; identifiant d’autorisation) : 1ʳᵉ passe : **une fuite réelle trouvée et corrigée** (une phrase d’un test synthétique d’unités partageait des 4-grammes avec un document ; une forme de date d’un test reprenait la forme d’une ligne de document) ; tests réécrits avec des exemples sans rapport, puis relancés. 2ᵉ passe : 27 lignes signalées, toutes qualifiées faux positifs (mots courants, valeurs de score, coordonnées et dates synthétiques, identifiant de test) ; 0 préfixe d’empreinte ni nom d’original, 0 chemin privé, 0 identifiant d’autorisation, 0 binaire, `git diff --check` propre sur les 41 fichiers du périmètre.

## 8. Intégration continue

Workflow « Private document translator », événement `pull_request` (PR brouillon n° 5), run `38381983787`, sur le commit `c1003b7` (code `62c33087cee540c9`, tests `b76c7cd037b2c196`, identiques à ceux testés localement, vérifié par `git archive`) : **success**.

| Job | Conclusion |
| --- | --- |
| backend | success |
| backend-integration-and-migrations | success |
| frontend | success |
| container-and-manifest-validation | success |
| private-acceptance | skipped (porte privée, non exécutable en CI publique) |
| manual-release-gate | skipped (porte manuelle, aucune mise en production) |

Le commit suivant ne modifie que ce rapport ; sa CI est suivie de la même façon. Une CI verte ne valide ni la qualité de traduction ni la conformité : les huit documents restent `REVIEW_REQUIRED`.
