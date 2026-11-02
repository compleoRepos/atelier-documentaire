# LOT 2.3 — Index des livrables

| | |
|---|---|
| Phase en cours | **A — audit, vérification du corpus et mesure de référence : terminée** (campagnes A et B achevées le 2 novembre 2026) |
| Base auditée | branche `feature/ocr-surya-20261030`, tête `8351d83ffe0b` (PR brouillon, non fusionnée) ; `main` inchangé |
| Code produit modifié pendant la Phase A | **aucun** (empreintes du code et des tests identiques avant et après) |
| Décision attendue | votre **validation explicite du diagnostic** avant la Phase B (corrections de fidélité) ; décisions détaillées au §12 du livrable 1 |
| Production | **NO-GO** inchangé |

> Revue humaine obligatoire sur chaque document, quel que soit le score.

## Livrables de la consigne et statut

| N° | Livrable | Fichier | Statut |
|---:|---|---|---|
| 1 | Rapport d’audit (architecture, chemin réel, performances avant optimisation, robustesse, corpus, défauts et décisions) | `01_RAPPORT_AUDIT.md` | **Phase A — livré, complet** (synthèse §0 ; campagne A §5 ; références B1 à B3 §6 ; arrêts du worker §7 ; tokenizer §8 ; défauts §9 ; décisions §12) |
| 2 | Rapport qualité OCR | — | Phase B/D (mesures OCR de référence déjà dans le livrable 1, §5 et §6) |
| 3 | Rapport traduction | — | Phase B/D (exige une validation humaine, non disponible) |
| 4 | Rapport DICE (F-L2-02, F-L2-03, D-DET-02) | — | Phase B (état avant correction dans le livrable 1) |
| 5 | Rapport reconstruction | — | Phase B (D-REC-01, D-REC-02) |
| 6 | Rapport performance | — | Phase C (référence avant optimisation dans le livrable 1, §5 à §8) |
| 7 | Benchmark avant/après | — | Phase C (le « avant » est le livrable 1) |
| 8 | Rapport cohérence bancaire (23 dossiers) | — | Phase D |
| 9 | Rapport de tests | `09_RAPPORT_TESTS.md` | **Phase A — état de référence livré** (y compris les 2 tests PostgreSQL rattrapés), complété à chaque phase |
| 10 | Plan de capacité | — | Phase C/D (aucun chiffre du moteur cible : non mesuré) |
| 11 | Recommandation finale | — | Phase D |
| A1 | Annexe : sources légales de documents réels remplis | `A1_SOURCES_DOCUMENTS_REELS.md` | **Phase A — livré** (recherche, rien n’a été téléchargé) |

## Conventions

Chaque chiffre porte une étiquette de preuve : **MESURÉ-S** (document synthétique), **MESURÉ-P** (document public réel, jamais une pièce de client), **LU** (code), **REPRIS** (rapport antérieur), **ESTIMÉ** (calcul dérivé), **NON MESURÉ**. Aucun document bancaire réellement rempli n’a été traité. Aucun texte de document n’a quitté la machine.

## Points clés de la Phase A

Le code audité passe ses tests, mais il n’est pas industriel sur le chemin réel. Délai moteur de 60 s codé en dur (D-ENG-01) ; blocs omis en silence (D-DET-02) ; dossier de 14 pièces non traduit en 2 heures, tâches tuées à 1 800 s (D-OPS-02) ; tâche perdue et document figé à chaque arrêt de worker sans grâce suffisante, y compris l’arrêt par défaut de Compose (D-OPS-01) ; Surya limité à une page à la fois et ralenti 3,27 fois en silence par une variable héritée (D-OCR-02, D-OCR-06) ; aucun golden sur le chemin Surya (D-REC-01) ; CI rouge sur deux audits de dépendances (D-SUP-01). Les références du LOT 2.2 sont reproduites. Aucune qualification humaine n’a eu lieu, et le moteur cible n’a jamais été mesuré.
