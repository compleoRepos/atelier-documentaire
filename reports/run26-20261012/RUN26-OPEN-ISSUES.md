# RUN26 — Défauts et questions ouverts

Ces points empêchent de déclarer le corpus conforme. Les corrections indiquées sont des **pistes, sans promesse de
résultat** : aucune n'a été mesurée. Tous les chiffres viennent des [exports anonymisés](documents/) du run de verdict.

## 1. Blocages de principe

| ID | Point ouvert | Conséquence | Ce qu'il faut pour le lever |
|---|---|---|---|
| OI-01 | **Aucune référence humaine** : ni traduction de référence, ni transcription des scans, ni revue des ajouts et omissions | Trois sous-composantes du score restent inconnues et comptent 0 : **plafond structurel de 84,2/100**. Le seuil de 94 est mathématiquement inatteignable | Des références produites ou validées par un humain autorisé, versionnées hors Git (privé), puis rejouées avec la méthode gelée |
| OI-02 | **Aucune validation humaine** des 8 documents | `REVIEW_REQUIRED` ×8 obligatoire ; `VALIDATED` impossible par construction | Revue humaine tracée (identité, version, date) via les API de revue existantes |
| OI-03 | **Qwen/vLLM non qualifié** | Interim (gpt-5-mini) reste un moteur temporaire de développement, utilisé sous autorisation, hors cloud privé, budget 32 768 tokens respecté | Endpoint, tokenizer et poids privés disponibles ; rejouer le corpus avec la même méthode |
| OI-04 | **Mise en production** | Bloquée tant que OI-01 à OI-03 et les défauts critiques ne sont pas levés | — |

## 2. Défauts critiques restants (105)

| Document | Défauts critiques run25e | Défauts critiques run26 |
|---|---|---|
| DOC-001 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 | `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 |
| DOC-002 | `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 | `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 |
| DOC-003 | aucun | aucun |
| DOC-004 | `LAYOUT_OVERFLOW` ×14, `PROTECTED_REGION_CHANGED` ×8, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `VISUAL_MASK_TOO_LARGE` ×1 | `LAYOUT_OVERFLOW` ×17, `PROTECTED_REGION_CHANGED` ×6, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `VISUAL_MASK_TOO_LARGE` ×1 |
| DOC-005 | `ENTITY_DIGITS_MISMATCH` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 | `ENTITY_DIGITS_MISMATCH` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1 |
| DOC-006 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1, `HALLUCINATION_UNIT_CHANGED` ×1, `LAYOUT_OVERFLOW` ×3, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×12, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1, `VISUAL_MASK_TOO_LARGE` ×12 | `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED` ×1, `HALLUCINATION_UNIT_CHANGED` ×1, `LAYOUT_OVERFLOW` ×3, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×12, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×1, `VISUAL_MASK_TOO_LARGE` ×12 |
| DOC-007 | `LAYOUT_OVERFLOW` ×8, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×2, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×3, `UNMAPPED_TABLE_CONTENT` ×1, `VISUAL_MASK_TOO_LARGE` ×2 | `LAYOUT_OVERFLOW` ×7, `PROTECTED_ENTITY_CHANGED` ×1, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TEXT_MASK_TOO_LARGE` ×2, `RENDER_TRANSLATED_TEXT_MISSING` ×1, `SCAN_TEXT_OVER_SOURCE_INK` ×4, `UNMAPPED_TABLE_CONTENT` ×1, `VISUAL_MASK_TOO_LARGE` ×2 |
| DOC-008 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 | `LAYOUT_OVERFLOW` ×2, `RENDER_SOURCE_TEXT_MISSING` ×1, `RENDER_TEXT_CLIPPED_OR_MISSING` ×1, `RENDER_TRANSLATED_TEXT_MISSING` ×1 |

| ID | Défaut | Ampleur (run de verdict) | Cause connue | Piste de correction |
|---|---|---|---|---|
| OI-05 | Débordement de la traduction (`LAYOUT_OVERFLOW`, blocs `FAILED: render_overflow`) | 29 alertes ; 29 blocs (DOC-004 17, DOC-007 7, DOC-006 3, DOC-008 2) | Cible française plus longue que la zone source à la taille de police minimale | Reformulation plus courte **soumise à revue humaine**. Pas de relance automatique « à longueur contrainte » : sur un texte juridique, une omission y serait indétectable |
| OI-06 | Masques trop larges (`RENDER_TEXT_MASK_TOO_LARGE`, `VISUAL_MASK_TOO_LARGE`) | 15 + 15 alertes, dont 12 + 12 sur DOC-006 | Le masque de blanchiment déborde sur des éléments graphiques voisins | Borner le masque au contour d'encre de la ligne, puis vérifier visuellement sur les planches privées |
| OI-07 | Encre source résiduelle sous la traduction (`SCAN_TEXT_OVER_SOURCE_INK`, blocs `FAILED: render_residual_source_ink`) | 10 alertes ; 10 blocs | Couverture incomplète du texte source ; sur DOC-007, aggravée par F25 (voir OI-15) | Extension du masque fondée sur l'encre réelle, avec preuve d'absence d'altération des régions protégées |
| OI-08 | Texte absent du rendu (`RENDER_TRANSLATED_TEXT_MISSING`, `RENDER_SOURCE_TEXT_MISSING`, `RENDER_TEXT_CLIPPED_OR_MISSING`) | 7 documents × 3 codes (une seule mesure, déclarée sous trois codes) ; compteur interne : 44 cibles | Refus de rendu réels (débordement, masque non sûr, encre résiduelle, écriture de droite à gauche) | Découle d'OI-05 à OI-07 et d'OI-12 |
| OI-09 | Régions protégées altérées (`PROTECTED_REGION_CHANGED`) | 6 alertes (DOC-004) | Masque ou texte inséré sur une région visuelle protégée | Exclusion stricte des régions protégées lors du rendu, puis audit des régions |
| OI-10 | Entités modifiées (`CRITICAL_ENTITY_MODIFIED`, `HALLUCINATION_ENTITY_MODIFIED`, `HALLUCINATION_UNIT_CHANGED`, `PROTECTED_ENTITY_CHANGED`) | 7 alertes (DOC-006 5, DOC-002 1, DOC-007 1) | Le modèle modifie une entité protégée ou une unité | Garde d'entités déjà active (blocs rejetés) ; revue humaine des cas restants |
| OI-11 | **Chiffre introduit non détecté par le produit** (`ENTITY_DIGITS_MISMATCH`, détecté par le scorecard seul) | 1 bloc (DOC-005), statut produit `TRANSLATED` | Dans une référence d'adresse, le modèle a remplacé un caractère lu comme une lettre par l'OCR par un chiffre (confusion probable « l »/« 1 »). Le garde d'entités du produit ne compare que les chiffres déjà présents dans la source | Nouvelle règle produit : tout chiffre **introduit** par la cible → `UNCERTAIN` et revue humaine. Non faite dans RUN26 : elle change le comportement pour d'autres cas (ordinaux, nombres écrits en lettres) et invaliderait le run de verdict ; elle doit être mesurée sur tout le corpus |
| OI-12 | Contenu de tableau non apparié (`UNMAPPED_TABLE_CONTENT`) | 1 alerte (DOC-007) | Cellule non rattachée à la structure de tableau | Analyse de structure de tableau sur scan |

## 3. Blocs non traduits ou incertains

| ID | Point | Ampleur | Piste |
|---|---|---|---|
| OI-13 | Le modèle renvoie la source inchangée (`FAILED: model_returned_source`) | 102 blocs (DOC-006 43, DOC-007 20, DOC-008 15, DOC-004 11, DOC-002 5, DOC-005 5, DOC-001 2, DOC-003 1) | Analyse par langue source. À rejouer avec le moteur cible (Qwen) avant toute conclusion |
| OI-14 | Blocs `UNCERTAIN` envoyés en revue humaine | 146 blocs : OCR non fiable 133, structure de formulaire ambiguë 12, écriture incohérente 1 | Revue humaine ; meilleure OCR (moteur de qualification, références de transcription) |
| OI-15 | **Perte collatérale de F25** (DOC-007) | 1 valeur correctement traduite n'est plus rendue : ses voisins, passés `UNCERTAIN`, gardent leur source, le masque ne s'étend plus et l'encre résiduelle est détectée | Dissocier l'extension du masque du statut des voisins, sous preuve de non-altération |
| OI-16 | Écriture de droite à gauche non rendue (`FAILED: render_rtl_shaping_unsupported`) | 3 blocs | Moteur de mise en forme bidirectionnelle (shaping) ; aujourd'hui refus sûr |
| OI-17 | Blocs gardés « sans contenu linguistique » (`NOT_TRANSLATABLE: no_linguistic_content`) | 141 blocs | Classement automatique, non vérifié par un humain |
| OI-18 | Garde d'entités rejetant la traduction (`FAILED: entity_guard_rejected`) | 3 blocs | Revue humaine |
| OI-19 | Masque jugé non sûr (`FAILED: render_mask_unsafe`) | 4 blocs | Voir OI-06 |

## 4. Défauts de qualité non détectés automatiquement

| ID | Point | Constat | Piste |
|---|---|---|---|
| OI-20 | Traduction cohérente en apparence mais fausse (DOC-004, un bloc) | Inspection visuelle des planches privées : bloc OCR qui mêle deux questions et du bruit, filet de tableau traversant le texte. La cible est complète et vérifiée par F26, mais elle n'a pas de sens. **Aucun contrôle ne le signale** | Segmentation des blocs sur les filets de tableau ; références humaines |
| OI-21 | Traductions de bruit OCR à confiance moyenne (DOC-004) | Des fragments OCR de confiance ≥ 0,60 (donc hors champ de F25) sont traduits ; leur « traduction » est une hallucination possible | Seuil et règle lexicale de F25 à réévaluer **avec** des transcriptions de référence |
| OI-22 | Noms, clauses, données bancaires | Contrôlés automatiquement **seulement pour leurs nombres** | Références humaines |

## 5. Preuves et outillage

| ID | Point | Détail | Piste |
|---|---|---|---|
| OI-23 | Origine des cibles de mémoire antérieures à RUN26 | 973 cibles du run de verdict viennent d'une génération antérieure à la traçabilité RUN26 : leur requête génératrice n'est pas traçable (provenance `TRANSLATION_MEMORY`, déclarée comme telle) | Régénérer le corpus (Interim sous autorisation valide, ou Qwen) pour une traçabilité complète requête par requête |
| OI-24 | **Historique Git** | Des valeurs issues des documents (montants, dates, un numéro de téléphone, des fragments OCR) figurent dans des commits **déjà poussés** par des runs précédents. RUN26 les a retirées de l'arbre courant, mais pas de l'historique | Réécriture d'historique et `push --force` sur les branches concernées : action destructive, **à décider par le responsable du dépôt** |
| OI-25 | Pas de garde anti-fuite automatique en CI | Le scanner RUN26 compare le dépôt au corpus privé : il ne peut pas tourner dans une CI qui n'a pas accès au corpus, et c'est voulu | Crochet pré-commit exécuté sur le poste privé, avec un index de n-grammes haché (pas de texte en clair) |
| OI-26 | Formatage global | `ruff format --check backend tools` signale 21 fichiers, tous antérieurs à RUN26 et inchangés. La CI ne lance pas ce contrôle. Tous les fichiers Python modifiés ou créés par RUN26 sont formatés | Formatage en masse dans un commit dédié, sans changement fonctionnel |
