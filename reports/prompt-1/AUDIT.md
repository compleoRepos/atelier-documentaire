# Audit d’industrialisation — Prompt 1

Date : 8 octobre 2026. Dépôt privé autorisé, base `6fb913a3a402e45c5813bf343fb85f26ef0e0e20`, branche exclusive `feature/prompt-1-industrialisation-20261008`. Architecture FastAPI/Angular conservée. Aucun changement de `main`, aucun cherry-pick de la branche Prompt 2.

## Conclusion et vocabulaire de preuve

**L’implémentation et les preuves techniques ne constituent pas une qualification bancaire.** `IMPLEMENTED` = code câblé ; `EXECUTED` = chemin réellement exécuté ; `TESTED` = assertions automatisées ; `MEASURED` = métrique instrumentée, en indiquant sa nature ; `VALIDATED` = validation sur vérité terrain adaptée. Le rapport de tests contient les résultats définitifs ; les rapports qualité/Golden distinguent les éléments non validés.

L’inspection réelle a retrouvé un IR, deux OCR locaux, classification explicable, garde-fous de requête Qwen, contexte atomique, glossaire/mémoire tenant-scopés, renderer PDF/DOCX, moteur de qualité, API de revue et gates de production. La baseline exécutée avant modifications était **167 tests Python techniques réussis**. Le preprocessing documentaire dédié et sa preview étaient absents. Aucun endpoint/tokenizer/poids Qwen privé, références humaines Golden ou identifiant de tenant Golden n’est fourni à cette exécution. Après décision utilisateur explicite, elles sont utilisées **uniquement** pour le provider temporaire Interim et des fixtures synthétiques non personnelles ; jamais pour le corpus réel. Voir INTERIM-TRANSITION.md.

## Exigences : couverture et qualification

« Technique » signifie testé avec fixtures ou véritables outils locaux, pas un PASS Qwen/Golden humain. « Corpus » signifie les originaux privés, pas des attendus humains. Les chiffres finaux sont centralisés dans TEST-REPORT et IMAGE-PREPROCESSING-REPORT.

| § | Exigence | État initial → livré | IMPLEMENTED / EXECUTED / TESTED | MEASURED / VALIDATED |
|---|---|---|---|---|
| 1 | Original immuable, SHA/métadonnées/version | existant partiel → SHA avant/après, métadonnées, processing copy | oui / oui / technique + corpus | SHA exact / intégrité validée, pas authenticité |
| 2–3 | Preprocessing avant OCR | absent → module dédié + ingestion API | oui / oui / technique + corpus | télémétrie / qualification OCR humaine non |
| 4 | Orientation 0/90/180/270 | absent → OSD local, correction selon confiance | oui / oui / OCR réel sur fixtures tournées | OSD et proxy OCR / pas calibration humaine |
| 5 | Deskew | absent → Hough + projection si preuve insuffisante | oui / oui / ± rotations contrôlées | angle/confiance instrumentés / robustesse universelle non |
| 6 | Perspective | absent → quadrilatère + homographie + garde anti-perte | oui / oui / fixture géométrique et dégradation réelle | matrice exacte / photos ambiguës refusées, pas qualification universelle |
| 7 | Bordures/marges | absent → crop de marges blanches seulement | oui / oui / contenu et protection aux bords | conservation géométrique / bord noir ambigu non supprimé |
| 8 | Bruit | absent → méthodes locales sélectionnées, autres méthodes exposées et testées | oui / oui / méthodes + bruit contrôlé | confiance avant/après / CER réel non |
| 9 | Fond | absent → normalisation illumination basse fréquence | oui / oui / unité + ombre contrôlée | proxy OCR / exactitude humaine non |
| 10 | Contraste | absent → CLAHE et alternatives, revert | oui / oui / tests de sélection et contraste réduit | proxy, pas taux d’exactitude / validation humaine non |
| 11–12 | Netteté/flou | absent → sharpen modéré, pas de reconstruction générative de lettres | oui / oui / filtres et blur contrôlé | variance Laplacien + proxy / deblur avancé non revendiqué |
| 13 | Binarisation | absent → Otsu/adaptive mean/adaptive Gaussian, pas aveuglément sur graphiques | oui / oui / méthodes | proxy / vérité terrain non |
| 14 | Lignes de tableaux | existant → détection sur source, coordonnées raster/PDF corrigées | oui / oui / grilles et bbox | géométrie / reconstruction finale propriétaire Prompt 2 |
| 15–18 | Cachets/signatures/masks IR | protections manuelles existantes → candidats couleur/contours + restauration pixels | oui / oui / conservation candidates/masques | candidats non calibrés / authentification jamais revendiquée |
| 19 | Cinq profils | absent → auto + clean/noisy/old/mobile/complex | oui / oui / six sélections dont auto | décisions/diagnostic / recette humaine non |
| 20–21 | Multi-version et score | absent → OCR baseline + candidats, original si baisse/perte | oui / oui / sélection/revert | confiance proxy pondérée / CER-WER nuls sans GT |
| 22 | Dataset | huit fichiers privés retrouvés → catalogue vérifié | oui / oui / chaque document testé | 8 documents/31 pages / originaux, pas Golden Expected |
| 23–24 | Images/dégradations | partiel → banc reproductible + rotations, blur, bruit, contraste, JPEG, ombre, perspective | oui / oui / banc et tests | résultats avant/après / seuil acceptable humain non défini |
| 25 | CER/WER/entités OCR | moteur de métriques existant, pas de GT réelle | oui / pas de mesure corpus avec GT / tests de métriques existants | null pour corpus / NOT_AVAILABLE_IN_ENVIRONMENT |
| 26 | Traduction langues/types | adaptateur privé et classifications existants, pas de modèle fourni | oui / OCR/offline local, doubles et Interim live synthétique EN-AR-ES→FR / technique | corpus modèle NOT_EXECUTED (confidentialité), Qwen indisponible |
| 27 | 32768 et tokenizer réel | garde existant renforcé : schéma tokenisé, constructeur, comptes/hash persistés | oui / doubles locaux / bornes requête complète | compteur GPT o200k_base/usage réel Interim + garde totale contractuelle ; vrai tokenizer Qwen absent |
| 28 | Chunking sémantique | existant conservé : unités pages/blocs/tableaux atomiques | oui / oui / historique + limites | overflow bloqué / longs tableaux non découpés arbitrairement |
| 29–30 | Contexte et décisions | existant renforcé : domaines, mémoires validées, décisions précédentes, style/pays fournis | oui / double + offline / technique | contexte borné / qualité linguistique réelle indisponible |
| 31 | Glossaires métier/client | moteur existant → cinq glossaires versionnés, overrides client | oui / oui / priorité/domaine | version tracée / seeds ne sont pas Golden ni mémoire humaine |
| 32 | Mémoire humaine | existant : DB tenant, entrées validées ; rejet des listes non validées renforcé | oui / oui / technique et accès | pas de fausse validation automatique / dictionnaire interne trusted conservé pour compatibilité |
| 33 | Entités/hallucination | placeholders, restauration et gates critiques conservés | oui / oui / tests d’invariants | exactitude des invariants textuels / OCR réel sans GT non garanti |
| 34–36 | Reconstruction/qualité/protection | existant incomplet ; travail de fidélité délégué Prompt 2 | oui existant / oui / tests renderer existants + corpus offline | scores techniques uniquement / recette documentaire humaine non |
| 37–38 | Golden et non-régression | framework existant ; chaque original testé, gates stricts inchangés | oui / pipeline technique / 8 cas privés | références humaines absentes, aucun faux PASS Golden |
| 39 | 10K à 32K+ | requête complète, total génération 8000/marge2768, circuit en violation | oui / oui / doubles Qwen et Interim + proxy synthétique | compteurs/usage Interim mesurés, Qwen réel non disponible |
| 40 | Sécurité | gates existants conservés ; limites image/TIFF/warp et blocage metadata ajoutés | oui / oui / attaques synthétiques | audit dépendances et contrôles techniques / AV privé non disponible |
| 41 | E2E | workflow existant + E2E raster réel, snapshots, revue obligatoire | oui / local offline / E2E technique | intégrité/download / E2E Qwen privé non |
| 42 | Neuf étapes UI | quatre étapes statiques → projection API d’après preuves | oui / oui / backend + Angular | native = non applicable ; contrôle exécuté ≠ qualité validée |
| 43 | Revue original/enhanced/candidat/diff | enhanced absent → panneau et endpoint authentifié versionné | oui / oui / race/revoke/version/tenant | preuve d’accès / appréciation documentaire humaine non |
| 44 | Audit | existant → version/profil/opérations/SHA preprocessing, tokens/hash privés persistés | oui / oui / tests/API | télémétrie sans texte/chemins locaux / qualification modèle non |
| 45 | Reproductibilité | versions, assets locaux/hash, seed dégradations, paramètres provider tracés | oui / oui / tests déterministes | pipeline reproductible selon versions / nondéterminisme modèle réel inconnu |
| 46 | Rapports | livrés dans reports/prompt-1 | oui | résultats définitifs liés, sans données personnelles |
| 47 | Ordre | audit, récupération/catalogue, implémentation, OCR, enquête privée, tests, corrections, rapports | exécuté | Qwen bloqué explicitement ; Interim live seulement sur fixtures synthétiques selon décision utilisateur |
| 48 | Ne pas altérer visuels/original | processing copy + candidats restaurés + original renderer | oui / oui / SHA et pixels sur fixtures | intégrité originale / détection exhaustive non validée |
| 49–50 | Definition of Done | technique achevée, qualification entière non acquise | voir TEST-REPORT | **NON QUALIFIÉ BANCAIREMENT** : Qwen/GT/cloud privé manquants |

## Corrections après audit contradictoire

- Conversion layout raster vers points PDF, en gardant les bbox source de l’IR.
- Limites de pixels vérifiées **avant** rendu/warp, orientation optionnelle fail-safe.
- Adaptateur TIFF multipage indépendant du renderer, intégrité originale et pixels testés.
- Aucun fallback offline en cas d’échec de l’inférence privée ; source conservée avec problème critique.
- Score réel `PreprocessingQualityScore` relié à Angular ; native OCR indiqué non applicable.
- URI et previews enhanced conservées dans des snapshots par version, pas de fallback vers l’analyse courante.
- Ancien test réutilisant explicitement `validated:false` corrigé pour exiger `validated:true` et vérifier le rejet de l’entrée non approuvée.

Les tests de régression correspondants sont présents. Les autres travaux de reconstruction/runs/fidélité restent explicitement la propriété de la branche Prompt 2 ; voir MERGE-INTERFACES.md.

## Ajout explicitement autorisé Interim

Provider séparé, pas un fallback. Entrée complète ≤22000 + max_completion_tokens total ≤8000 + marge2768 ≤32768 ; contrat officiel vérifié, sondes caps16/64, contrôles post-call/calibration/circuit. Garde SHA corpus et allowlist payload/context, production/private interdite, credentials serveur, UI/audit explicites. Les 8 SHA réels ont été refusés avant réseau. Détails et preuves observées dans INTERIM-TRANSITION.md ; aucune référence humaine fabriquée.
