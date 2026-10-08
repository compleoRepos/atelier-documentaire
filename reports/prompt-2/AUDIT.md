# Audit et finalisation du moteur de fidélité — prompt 2

**Base auditée :** `6fb913a3a402e45c5813bf343fb85f26ef0e0e20`  
**Branche exclusive :** `feature/prompt-2-fidelite-20261008`  
**Date :** 8 octobre 2026. Aucun merge ni changement de `main`. Clone et dépendances isolés. Architecture FastAPI/Angular conservée.

## Méthode et frontière de responsabilité

Les deux prompts joints ont été lus intégralement avant les modifications. Les modules `pipeline.py`, `layout.py`, `render_metrics.py`, configuration, contexte, traduction, tests et architecture ont été inspectés. La baseline complète préexistante a été lancée avant intégration. L’exécution 1 conserve la propriété preprocessing, profils OCR, Qwen/contexte/glossaires/mémoire et API/UI. Cette branche complète ingestion OOXML, reconstructions, tableaux, mesures et objets visuels protégés. Les interfaces de merge sont dans `ARCHITECTURE.md` et le résultat machine.

## État constaté avant intervention

| Exigence | État initial vérifié | Preuve / dette | Intervention prompt 2 |
| --- | --- | --- | --- |
| Architecture API, tenants, storage, revue, Celery | EXISTANT ET FONCTIONNEL techniquement | Tests API/E2E/sécurité présents ; pas de cloud bancaire validé | Conservée |
| Original SHA PDF/image | EXISTANT ET FONCTIONNEL | SHA dans IR | Vérification du SHA avant reconstruction, refus chemins/aliases écrasant la source |
| DOCX ordre corps/tables, source_ref, images | EXISTANT MAIS INCOMPLET | Tables top-level, en-têtes/pieds par section, nested tables omises | Analyse XML hiérarchique et parties header/footer distinctes |
| Runs Word | EXISTANT MAIS À CORRIGER | `_replace_docx_text` mettait tout dans le premier `w:t`, vidait les autres | Redistribution proportionnelle traçable, aucun run vidé brutalement |
| Styles internes traduits | EXISTANT MAIS INCOMPLET | XML conservé mais attribution sémantique inconnue | Multistyles : candidat avec trace et REVIEW_REQUIRED ; score sémantique de style reste null |
| Hyperlinks/bookmarks/fields/tabs/breaks | EXISTANT MAIS INCOMPLET | Nœuds gardés, frontières textuelles non protégées | Métadonnées, résultat de champ protégé, refus prudent des changements ambigus |
| Package DOCX | EXISTANT MAIS INCOMPLET | Sauvegarde python-docx réécrit le package | Copie des membres non modifiés, seules valeurs `w:t` et `xml:space` modifiées |
| Tables DOCX/fusions/layout | EXISTANT MAIS INCOMPLET | Déduplication de cellules fusionnées, hiérarchie limitée | Lignes/cellules/paragraphes/runs, gridSpan/vMerge/rowSpan, nested tables et styles XML |
| PDF layout/table candidates | EXISTANT ET FONCTIONNEL comme heuristique | Géométrie native/raster, fusions candidates ; pas vérité métier | Enrichissement style/padding/alignement avec provenance candidate |
| Reconstruction tables PDF | EXISTANT MAIS À CORRIGER | Redactions blanches et bbox de glyphes ; tableaux traités comme blocs | Unité cellule, zone intérieure/padding/alignement, fills/bordures conservés, préflight et rollback |
| Mesure candidate tables | EXISTANT MAIS À CORRIGER | `table_structure` copié de l’IR dans résultat ; métrique PDF null | Extraction source/candidat indépendante, cellules/fusions/fills/borders et texte cible réel |
| Protection signatures/cachets/logo/QR | EXISTANT MAIS INCOMPLET | Zones explicites, conservation des images ; pas identification exhaustive | `protected_visual_regions`, images/widgets/vecteurs candidats, coordonnées source, editable=false |
| Authenticité/signature cryptographique | ABSENT et non revendiqué | Un candidat PDF dérivé ne conserve aucune preuve d’authenticité | Toujours `authenticity_verified=false` ; rien généré/authentifié |
| Conversion DOCX réelle | EXISTANT ET FONCTIONNEL | LibreOffice isolé, timeouts, dimensions/pages/previews | Conservée et testée, overflow/pagination vers revue |
| Validation visuelle | EXISTANT MAIS INCOMPLET | Previews, pixel/geometry ; première dimension utilisée pour tous les masques | Dimensions par page, masques glyphes bornés, original/translated/diff/metrics/result privés |
| Scores qualité | EXISTANT MAIS INCOMPLET | Certains providers privés absents, null correct | Résumé STRUCTURE/LAYOUT/TEXT/ENTITY/TABLE/VISUAL ; GLOBAL null sans validations/calibration |
| Statut référence corpus | EXISTANT MAIS À CORRIGER | Provider renvoie `not_available`, contrat pipeline attend `not_evaluated` | Normalisation au niveau pipeline, pas modification du test ; brut conservé dans quality_contract |
| Preprocessing OCR avancé | EXISTANT MAIS INCOMPLET | OCR local et heuristiques ; chaîne avancée non présente dans cette base | Propriété branche 1, pas seconde implémentation concurrente |
| Qwen privé / contexte / 32K | EXISTANT MAIS INCOMPLET en environnement | Adapter fail-closed/tokenizer local, tests de transport existants ; endpoint/poids/tokenizer exact absents | Audit et tests de seuils synthétiques, aucun appel LLM ni API publique |
| Golden Framework | EXISTANT ET FONCTIONNEL comme workflow | Référence humaine requise ; huit originaux privés disponibles | SHA préservés ; traitement technique hors ligne, aucune référence créée |
| Interface reviewer | EXISTANT ET FONCTIONNEL techniquement | Original/candidat/diff, édition/rejet/commentaire/attestation, 12 tests Angular | Conservée ; branche 1 peut étendre OCR/étapes |
| Audit/observabilité | EXISTANT MAIS INCOMPLET industriellement | Audit tenant/user, versions et métriques, pas GPU privé | renderer_version et preuves ajoutés, pas simulation GPU |

## Exécution honnête et composants indisponibles

- Aucun `OPENAI_API_KEY`/`OPENAI_API_BASE` utilisé ; aucun modèle public téléchargé ; aucune réponse live Qwen créée.
- Tesseract 5.3.4 et traineddata locaux installés pour l’OCR technique ; le premier run baseline a été lancé avant sa disponibilité, ses neuf échecs sont conservés.
- Aucun endpoint `TRANSLATOR_PRIVATE_AI_*`, tokenizer Qwen exact ou poids privés n’étaient configurés : **NOT_AVAILABLE_IN_ENVIRONMENT** pour validation live/tokenisation Qwen.
- Aucun Golden humain, provider embedding/judge privé ou baseline bancaire approuvée : **NOT_AVAILABLE_IN_ENVIRONMENT**. Les doubles déjà présents dans les tests sont des tests de contrat, pas preuves live.
- DOCX multistyle et frontières hyperlink/bookmark/champ/tab/break ne sont jamais promus à une réussite sémantique. Les champs et frontières ambigus restent en revue ; édition manuelle requise.
- Scans : signature/cachet dans une image de page complète requiert annotation humaine ; une page entière n’est pas mensongèrement labellisée « signature ». Pour protéger les pixels originaux, utiliser les zones source, jamais les coordonnées non inversées d’une copie OCR améliorée.

## Risques et dette résiduelle

1. Détection tables heuristique, multi-tables disjointes/formulaires complexes/non-rectangular merges encore prudents. La géométrie mesurée ne valide pas le sens métier.
2. Layout DOCX dépend des polices LibreOffice, pas moteur Word certifié. Les paragraphes répétés et ancrages multi-pages peuvent rester non mappés ; la pagination est néanmoins rendue réellement.
3. Attribution sémantique des styles non résolue sans alignement validé ; la redistribution ne fabrique pas un alignement.
4. RTL PDF non configuré est bloqué plutôt que produire des glyphes incorrects. Complex typography nécessite un moteur shaping validé.
5. Font shrinking PDF borné avec revue si réduction importante ; aucune adaptation DOCX automatique qui détruit les propriétés originales.
6. Calibration OCR/linguistique/visuelle, robustesse corpus élargi, tests vrais Private Cloud et validation humaine restent nécessaires avant banque.
7. Dériver un PDF peut invalider sa signature cryptographique ; la présence visuelle ne constitue ni vérification ni certification.
8. Certaines dépendances émettent des avertissements de dépréciation (PyMuPDF alias fitz, Pillow getdata, Starlette/httpx, Alembic). Pas de suppression de tests pour masquer ces avertissements.

Les résultats finaux exécutés, mesurés et validés techniquement sont détaillés dans `TEST_REPORT.md` et `DOCUMENT_FIDELITY_REPORT.md`. « Exécution terminée » ne signifie pas certification bancaire.

### Cas limites non certifiés

Les visuels dessinés dans les cellules peuvent être indiscernables des traits/fills du tableau ; les signatures/cachets vectoriels internes exigent annotation explicite avant remplacement. La détection automatique ne doit pas être interprétée comme couverture exhaustive. Les PDF à rotation native, crop complexe, plusieurs grilles disjointes, annotations ou fontes privées non disponibles nécessitent tests/calibration spécifiques ; cette livraison ne les certifie pas. La bibliothèque conserve les objets source, mais leur identité et la protection de tout symbole non détecté restent inconnues.

## Relecture indépendante et corrections de fin d’exécution

Une relecture read-only supplémentaire a identifié des points concrets. Les corrections suivantes ont été implémentées puis exercées dans `test_audit_guards_prompt2.py` et la non-régression finale :

- Paragraphes dans `w:sdt/w:sdtContent`, `w:ins` et wrappers génériques désormais parcourus ; parties footnotes/endnotes/comments incluses avec références numériques et package original conservé.
- Un bloc source inchangé disparu du candidat est maintenant une issue critique même si un autre bloc est traduit ; le dénominateur des traductions reste séparé.
- Appariement textuel limité à la même page et aux frontières de mots ; `Totalement` ne peut plus valider `Total` ; position départ utilisée pour départager les doublons.
- Vecteurs internes aux cellules désormais protégés sauf preuves précises de géométrie de tableau (traits axis-aligned alignés aux bords ou rectangles exacts). Images/signatures candidat ne sont pas assimilées aux fills.
- Régions protégées validées aussi dans l’API de mesure, contre dimensions réelles de la page ; bbox hors page donne measured=false/preserved=null et issue critique, jamais comparaison du padding PIL.
- Pagination PDF lue dans le fichier réellement sauvegardé, sans booléen true recopié ; la preuve réouvre également source/candidat.
- Sur le corpus, un objet graphique source dépassant le bord de page a déclenché un échec explicite d’analyse. Les **détections automatiques** sont désormais intersectées avec la partie visible de la page originale avec `source_object_bbox` et `clip_provenance`, en émettant une warning. Les **annotations utilisateur** hors page restent rejetées. Aucun original n’est modifié. La reconstruction avec rotation PDF native et changement de texte est bloquée en revue tant qu’un mapping validé n’est pas fourni.

Le rollback DOCX a aussi été questionné : cette livraison conserve volontairement des **candidats partiellement appliqués mais explicitement REVIEW_REQUIRED** lorsque certaines unités sont ambiguës, tout en laissant les unités refusées et l’original intacts. Il ne s’agit pas d’un artefact approuvé/livrable automatiquement. La granularité par paragraphe est une décision de contrat, pas une certification de document complet ; un consommateur doit impérativement respecter quality/status/issues. Le stockage et la revue API existants le font. Un mode atomique de document complet peut être ajouté si requis par la politique bancaire, sans confondre redistribution candidate et approbation.
