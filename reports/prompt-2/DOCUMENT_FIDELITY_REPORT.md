# Rapport de fidélité documentaire — prompt 2

## Portée et méthode

Mesures effectuées sur **fixtures synthétiques de renderer**, avec cibles explicitement fixées pour le test. Elles ne sont ni traductions live Qwen ni Golden humains. L’implémentation avant est chargée directement depuis le commit commun `6fb913a3a402e45c5813bf343fb85f26ef0e0e20` par `git show`; elle n’est pas reconstituée par imitation. Les candidats après passent par les fonctions intégrées du dépôt.

Outil reproductible :

```bash
PYTHONPATH=backend .venv/bin/python tools/prompt2_fidelity_measure.py \
  --out test-report/prompt-2/synthetic
# Option corpus privé disponible, sans référence inventée :
PYTHONPATH=backend .venv/bin/python tools/prompt2_fidelity_measure.py \
  --corpus --out test-report/prompt-2/corpus-measured
```

La preuve brute `measurements.json`, les DOCX/PDF candidats, rendus et diffs sont dans `test-report/prompt-2/release-final-synthetic/`, exclu de Git. Les seuls agrégats/données synthétiques versionnés sont `SYNTHETIC_MEASUREMENTS.json`.

## DOCX : runs et styles

Fixture originale : trois runs `Employee ` (gras), `salary ` (italique), `information` (taille explicite), suivis d’une table fusionnée et d’en-tête/pied de page.

| Mesure réelle | Avant | Après |
| --- | --- | --- |
| Runs du paragraphe | 3 | 3 |
| Runs contenant du texte | **1** | **3** |
| Texte run 1 | `Informations salariales employé` | `Informations ` |
| Texte run 2 | vide | `salariales ` |
| Texte run 3 | vide | `employé` |
| Blocs modifiés | 5 | 5 |
| Pages rendues LibreOffice | 1 | 1 |
| Package OOXML hors `w:t`/`xml:space` | identique | identique |
| Layout géométrique réel | 0.9948164713 | 0.9952754560 |
| Score sémantique d’attribution style | null | **null** |
| Attribution automatique validée | non | **non — REVIEW_REQUIRED** |

**Interprétation :** la conservation du XML seule aurait laissé croire que le style était préservé alors que tout le texte héritait du premier run. Le nouveau moteur garde l’occupation des runs, mais la redistribution proportionnelle ne peut garantir quel mot traduit correspond à quel mot source. Le candidat est traçable ; `DOCX_MULTI_STYLE_BOUNDARY_AMBIGUOUS` et `DOCX_STYLES_UNVERIFIED` exigent revue.

Le rendu synthétique après a été inspecté visuellement : gras/italique distincts, tableau dans sa structure, en-tête/pied préservés. Cela constitue une inspection technique du rendu, pas approbation linguistique/humaine Golden.

### Invariants OOXML supplémentaires testés

- Runs, bold/italic/underline, polices/taille/couleur/highlight, paragraph properties et numbering préservés par canonisation indépendante.
- Champs simples/complexes : résultats source protégés ; changement ambigu refusé.
- Hyperlinks, relationships, bookmarks, tabs, line/page breaks : structure conservée, pas texte aplati ni déplacement silencieux des frontières.
- Tables horizontal/vertical merges, `gridSpan`, `vMerge`, largeur colonnes, hauteur lignes, bordures/shading/header rows, cellules vides, paragraphes multiples et nested tables.
- Parties header/footer distinctes et media/custom package parts ; les membres non modifiés sont conservés.
- Un changement de taille dans le candidat est détecté par `OOXML_NON_TEXT_STRUCTURE_CHANGED`.
- Un candidat DOCX ajoutant des pages est détecté par la conversion réelle (`RENDER_PAGE_COUNT_CHANGED`), pas comptage logique copié.

## PDF : cellules, bordures et couleurs

Fixture : tableau natif 2×2, fond jaune, bordures bleues, texte source, image originale bleue hors tableau. Cibles : quatre textes synthétiques `Texte cellule 00/01/10/11`.

| Mesure indépendante du fichier candidat | Avant | Après |
| --- | --- | --- |
| Blocs modifiés | 4 | 4 |
| Débordements | 0 | 0 |
| Unités de rendu cellule | **0** | **4** |
| Invariants cellules/fusions/bordures/fill | **0.0 — non conservés** | **1.0 — conservés techniquement** |
| Textes cibles vus dans les cellules correspondantes | 4/4 | 4/4 |
| Layout géométrique réel | 0.7661128665 | 0.8061197983 |
| Similarité raster hors masques glyphes | 0.9997757167 | 0.9999993021 |
| Pixels du visuel protégé | identiques | identiques |
| Authenticité du visuel | non vérifiée | **non vérifiée** |

La redaction blanche legacy altérait les fills ; le nouveau moteur conserve les dessins originaux, efface seulement les zones textuelles nécessaires et replace le texte dans la zone intérieure de la cellule. Le rendu après a été inspecté : grille bleue, fond jaune, texte dans chaque cellule et visuel source inchangés.

**Attention :** le score layout reste inférieur à 1, car il mesure les déplacements/dimensions réels de glyphes ; il n’est pas forcé à 1 parce qu’il n’y a pas d’overflow. Les candidats de tables restent sémantiquement non validés. Une excellente moyenne raster ne suffit pas à certifier un document : les tests adversariaux détectent séparément la disparition d’une table, le changement de fill et l’absence de texte cible dans sa cellule.

### Préflight et sécurité du rendu

- Test de fit sur document scratch avant suppression de la source ; overflow conserve le texte original.
- Transaction par cellule/bloc avec checkpoint et rollback si insertion finale diverge.
- Refus des multi-cell links, cellules non rectangulaires/overlapping ou texte natif cellule non couvert par l’IR.
- Widgets/visuels protégés : remplacement bloqué si intersection ; source pixels jamais générés/authentifiés.
- Source SHA vérifié, chemin source/out et symlink/hardlink alias refusés.
- Réduction typographique bornée, avertissement de revue si importante ; RTL non configuré bloqué.
- Masques graphiques bornés aux glyphes et dimensions originales de chaque page, pas cellules/page entières.

## Corpus réel privé

Les huit PDF originaux (31 pages) ont été récupérés depuis l’archive confidentielle autorisée et conservés sans altération. Le corpus original, métadonnées, OCR, IR, candidats et previews ne sont pas versionnés. Les tests `golden_dataset` servent ici uniquement de **traitement technique hors ligne** : toute traduction absente reste `UNTRANSLATED` / `REVIEW_REQUIRED`, références humaines et scores linguistiques inconnus.

Le décompte final exécuté et la preuve SHA/couverture se trouvent dans `TEST_REPORT.md` et les artefacts privés. Aucun de ces tests n’établit une référence Golden validée.

## États de preuve

| Domaine | IMPLEMENTED | EXECUTED / TESTED | MEASURED | VALIDATED |
| --- | --- | --- | --- | --- |
| Reconstruction DOCX/PDF ciblée | oui | tests renderer/integration | structure, texte candidat, rendu/pixels | techniquement sur fixtures |
| Cohérence sémantique des styles | redistribution sans faux alignement | cas ambigu en revue | inconnue | non |
| Identification exhaustive signature/cachet/QR | candidats + annotations | conservation originaux testée | pixels zones explicites | identité/authenticité non |
| OCR corpus | moteur local existant | traitement technique | couverture réelle | précision humaine non |
| Traduction Qwen privée | adapter existant | NOT_AVAILABLE_IN_ENVIRONMENT live | tokenizer exact indisponible | non |
| Golden référence humaine | workflow existant | aucune référence créée | inconnu | non |
| GLOBAL_SCORE / certification bancaire | non certifié | jamais auto-PASS | null | non |

**Conclusion :** les défauts prioritaires du renderer ont été corrigés et leur progrès mesuré ; les inconnus indispensables à une recette bancaire restent explicitement bloquants.
