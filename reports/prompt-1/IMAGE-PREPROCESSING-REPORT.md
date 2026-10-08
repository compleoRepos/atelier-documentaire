# Preprocessing images — mesures locales finales

**Ces mesures ne sont ni CER/WER ni taux d’exactitude.** Source originale inchangée pour les huit documents. Aucune référence humaine disponible, aucun Qwen réel utilisé. Le passage final exécute le commit de code `69be1300451f48d4c2847549d077e84ee9f5dd01`.

## Passage final du corpus réel

31 pages, 29 paires de confiance mesurables ; 10 améliorations strictes, 19 égalités. 21 sélections de l’original. CER, WER, exactitude noms/dates/nombres/références : **null**.

| Cas | Pages | Profils sélectionnés | Variantes évaluées | Confiance avant (moyenne) | Après (moyenne) | Candidats visuels | SHA original |
|---|---:|---|---:|---:|---:|---:|---|
| DOC-001 | 2 | complex_document, noisy_scan | 7 | 0.8698 | 0.8698 | 16 | inchangé |
| DOC-002 | 1 | complex_document | 4 | 0.7931 | 0.7983 | 4 | inchangé |
| DOC-003 | 1 | complex_document | 4 | 0.9366 | 0.9366 | 1 | inchangé |
| DOC-004 | 2 | complex_document | 8 | 0.7684 | 0.7775 | 3 | inchangé |
| DOC-005 | 2 | complex_document | 8 | 0.8592 | 0.8663 | 3 | inchangé |
| DOC-006 | 16 | complex_document | 63 | 0.9244 | 0.9252 | 994 | inchangé |
| DOC-007 | 5 | clean_scan, complex_document, noisy_scan | 17 | 0.8375 | 0.8472 | 7 | inchangé |
| DOC-008 | 2 | complex_document | 8 | 0.9123 | 0.9141 | 8 | inchangé |

Les moyennes ci-dessus sont arithmétiques sur les pages disponibles ; à l’intérieur d’une page, la confiance OCR est pondérée par la longueur des blocs. Elles ne sont pas comparables à une exactitude humaine. Un candidat visuel peut recouvrir plusieurs éléments ou être un faux positif ; aucun n’est authentifié.

## Mesures par page finales

| Cas/page | Profil | Variante retenue | Confiance avant | Après | Caractères avant | Après | Blocs avant | Après |
|---|---|---|---:|---:|---:|---:|---:|---:|
| DOC-001/1 | complex_document | original | 0.8424 | 0.8424 | 457 | 457 | 13 | 13 |
| DOC-001/2 | noisy_scan | original | 0.8972 | 0.8972 | 921 | 921 | 28 | 28 |
| DOC-002/1 | complex_document | v01 | 0.7931 | 0.7983 | 906 | 875 | 20 | 19 |
| DOC-003/1 | complex_document | original | 0.9366 | 0.9366 | 677 | 677 | 11 | 11 |
| DOC-004/1 | complex_document | original | 0.8679 | 0.8679 | 2421 | 2421 | 93 | 93 |
| DOC-004/2 | complex_document | v02 | 0.6690 | 0.6871 | 1595 | 1632 | 61 | 62 |
| DOC-005/1 | complex_document | v01 | 0.8404 | 0.8507 | 1341 | 1342 | 34 | 35 |
| DOC-005/2 | complex_document | v03 | 0.8779 | 0.8820 | 927 | 924 | 31 | 31 |
| DOC-006/1 | complex_document | original | 0.8990 | 0.8990 | 930 | 930 | 39 | 39 |
| DOC-006/2 | complex_document | original | 0.9208 | 0.9208 | 782 | 782 | 37 | 37 |
| DOC-006/3 | complex_document | original | 0.7575 | 0.7575 | 167 | 167 | 20 | 20 |
| DOC-006/4 | complex_document | original | 0.9217 | 0.9217 | 1515 | 1515 | 36 | 36 |
| DOC-006/5 | complex_document | original | 0.9442 | 0.9442 | 1872 | 1872 | 28 | 28 |
| DOC-006/6 | complex_document | original | 0.9214 | 0.9214 | 1641 | 1641 | 35 | 35 |
| DOC-006/7 | complex_document | v02 | 0.9320 | 0.9353 | 2331 | 2317 | 38 | 38 |
| DOC-006/8 | complex_document | original | 0.9433 | 0.9433 | 2471 | 2471 | 41 | 41 |
| DOC-006/9 | complex_document | original | 0.9491 | 0.9491 | 2246 | 2246 | 33 | 33 |
| DOC-006/10 | complex_document | v03 | 0.9339 | 0.9371 | 2204 | 2203 | 38 | 38 |
| DOC-006/11 | complex_document | v02 | 0.9400 | 0.9468 | 2321 | 2285 | 43 | 36 |
| DOC-006/12 | complex_document | original | 0.9501 | 0.9501 | 2378 | 2378 | 34 | 34 |
| DOC-006/13 | complex_document | original | 0.9508 | 0.9508 | 2352 | 2352 | 34 | 34 |
| DOC-006/14 | complex_document | original | 0.9511 | 0.9511 | 1725 | 1725 | 29 | 29 |
| DOC-006/15 | complex_document | original | 0.9409 | 0.9409 | 1714 | 1714 | 37 | 37 |
| DOC-006/16 | complex_document | original | 0.9343 | 0.9343 | 1151 | 1151 | 24 | 24 |
| DOC-007/1 | complex_document | v02 | 0.7695 | 0.7797 | 3175 | 3228 | 54 | 57 |
| DOC-007/2 | clean_scan | original | null | null | 0 | 0 | 0 | 0 |
| DOC-007/3 | complex_document | v03 | 0.8388 | 0.8578 | 3883 | 3709 | 48 | 47 |
| DOC-007/4 | clean_scan | original | null | null | 0 | 0 | 0 | 0 |
| DOC-007/5 | noisy_scan | original | 0.9041 | 0.9041 | 2426 | 2426 | 32 | 32 |
| DOC-008/1 | complex_document | v03 | 0.9087 | 0.9123 | 1735 | 1734 | 44 | 44 |
| DOC-008/2 | complex_document | original | 0.9159 | 0.9159 | 1125 | 1125 | 31 | 31 |

## Dégradations contrôlées finales

Toutes dérivent de DOC-001/page-1, avec seed de bruit 20261008. Elles ne possèdent pas de transcription humaine de référence. Le seuil de récupération linguistique acceptable demeure non évalué ; les colonnes sont des observations techniques.

| Cas | Variante retenue | Confiance avant | Après | Caractères avant | Après | CER/WER | Qualification |
|---|---|---:|---:|---:|---:|---|---|
| rotation_5 | v01 | 0.6812 | 0.8335 | 313 | 370 | null | proxy seulement |
| rotation_10 | v01 | 0.5686 | 0.8285 | 131 | 364 | null | proxy seulement |
| rotation_90 | v01 | 0.3007 | 0.4446 | 85 | 127 | null | proxy seulement |
| rotation_180 | original | 0.3828 | 0.3828 | 334 | 334 | null | proxy seulement |
| rotation_270 | original | 0.7318 | 0.7318 | 323 | 323 | null | proxy seulement |
| blur | original | 0.4179 | 0.4179 | 173 | 173 | null | proxy seulement |
| noise | v01 | 0.7867 | 0.7978 | 380 | 397 | null | proxy seulement |
| low_contrast | original | 0.8343 | 0.8343 | 382 | 382 | null | proxy seulement |
| jpeg | original | 0.7668 | 0.7668 | 373 | 373 | null | proxy seulement |
| shadow | v01 | 0.8097 | 0.8924 | 40 | 59 | null | proxy seulement |
| perspective | v03 | null | 0.8183 | 0 | 334 | null | proxy seulement |

## Moteurs, répétitions et conservation

- Corpus final : Tesseract local, versions 5.3.4, langues installées utilisées : ara, deu, eng, fra, ita, nld, spa.
- Dégradations finales : Tesseract local ara/eng/fra/spa, OpenCV sur copies ; original/version source intacte.
- Premier banc exploratoire : 8 PDF/31 pages et 11 dégradations, 1708.1 secondes. Il précédait les derniers garde-fous de crop/perspective et l’adaptation layout ; ses métriques ne sont pas revendiquées comme celles du code final. Le tableau ci-dessus provient du dernier passage complet et les dégradations ont été rejouées sur le code final.
- Rejeu des 11 dégradations sur code final : 49.0 secondes.
- Profils et méthodes : auto/clean/noisy/old/mobile/complex ; OSD, deskew Hough/projection, perspective conservatrice, crop blanc sans perte, débruitage, CLAHE/contraste/fond, sharpen modéré et binarisations. Les protections interdisent un nettoyage aveugle des cachets/logos/photos.
- Auto = sélection conservative selon diagnostic ; chaque page n’est pas forcée à subir tous les filtres. Refus/revert et identité sont des résultats valides, pas une amélioration OCR fabriquée.
- SHA fichier, matrices inverses et bbox source vérifiés sur les 31 pages finales. L’original reste la base du renderer ; selected est uniquement l’entrée OCR.
- Artefacts confidentiels : dataset/preprocessing/final/, dataset/regression/final/, test-report/prompt-1/ ; non versionnés.
- Limites : détection non exhaustive des signatures/cachets, frontières ambiguës refusées, pas de CER/WER réel, pas de validation bancaire.
