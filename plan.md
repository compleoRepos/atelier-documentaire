# Plan d’implémentation — plateforme documentaire privée

## Contraintes et périmètre

Le cahier des charges fourni est la référence. L’application BTP déjà présente au dépôt reste inchangée. La nouvelle plateforme est isolée dans `ai-document-translator/`, sur une branche dédiée, avec livraison par PR et archive. Aucun original, texte extrait, résultat traduit ou donnée personnelle n’est commité ni publié. Le déploiement cible est un Cloud Privé bancaire, pas l’hébergement public Interim. Le Sandbox sert uniquement de laboratoire de développement local.

L’ordre est impératif : inventaire des huit PDF, classification et matrices, premiers cas Golden, moteur documentaire exécutable, puis interface Angular. La consultation visuelle initiale est une analyse des pièces jointes dans cette tâche ; aucun fournisseur public de traduction n’est appelé par le produit.

## Architecture et mise en œuvre

- **Backend Python 3.12 / FastAPI / Pydantic / SQLAlchemy** : contrôle des fichiers, authentification à rôles, isolation tenant, persistance des métadonnées et audit, gestion des jobs.
- **Représentation structurée** : pages, coordonnées, ordre de lecture, blocs, cellules, texte, confiance et provenance. Le document est une structure, pas une chaîne envoyée en bloc au LLM.
- **Documents** : extraction PDF native avec PyMuPDF ; OCR local de pages scannées et images. Adaptateur OCR Tesseract réellement testable localement, adaptateur PaddleOCR optionnel pour le déploiement privé. DOCX conserve le conteneur et la structure des paragraphes/tableaux, avec réserve explicite sur sa pagination dépendante du logiciel de rendu. Aucun moteur OCR n’est présenté comme calibré sans annotations humaines.
- **IA privée** : interface TranslationEngine ; adaptateur compatible vLLM/Qwen à endpoint privé explicitement autorisé, sans redirection HTTP ni télémétrie. Tokenizer local du modèle obligatoire pour l’inférence, enveloppe complète comptée avant chaque appel et plafond de 32768 tokens. Aucun basculement vers un fournisseur public.
- **Contexte** : unités sémantiques atomiques, glossaire tenant, mémoire uniquement validée, entités protégées, décisions et contexte pertinent limité. Les blocs/tableaux trop grands ne sont pas découpés arbitrairement : revue requise.
- **Mode hors ligne** : réutilisation exacte de traductions approuvées et de termes contrôlés ; les segments inconnus sont signalés, jamais simulés comme traduits. Le moteur privé n’est pas réputé opérationnel sans endpoint et modèle disponibles.
- **Reconstruction Python** : conserve les dimensions PDF et fond graphique ; réinsère le texte dans les zones d’origine ; réduit la taille dans une borne configurable ; tout débordement bloque la validation. Zones protégées pour signatures/cachets ; leur reconnaissance exhaustive n’est pas garantie et exige une revue. Les originaux restent immuables.
- **Qualité** : intégrité des nombres/références, couverture des blocs, structures, pagination et débordement ; images original/traduit/diff. CER/WER, fidélité et sémantique sont `non mesurés` sans références, jamais remplacés par des scores fictifs. Une différence pixel brute n’est pas une métrique de fidélité linguistique.
- **Validation humaine** : corrections, approbation/rejet, zones protégées, promotion explicite et versionnée en Golden Reference, alimentation contrôlée de la mémoire. La modification d’entités critiques, un segment non traduit ou un débordement interdit la finalisation automatique.
- **Déploiement** : Docker Compose PostgreSQL/Redis/MinIO/API/worker/frontend ; Kubernetes/Helm et policies réseau. Production exige secrets propres, stockage privé, modèle/tokenizer locaux et ingress TLS. Pas de déploiement PROD ni de publication dans cette tâche.

## Structure

`backend/app/` contient domain, core, documents, ai/context, ai/translation, ai/quality, infrastructure, application, api et workers. `backend/tests/` contient unit, integration, e2e, golden_dataset, regression et security. `frontend/` est une application Angular autonome. `dataset/input`, `expected`, `metadata`, `golden` restent locaux et exclus du Git. `tools/` fournit inventaire, rapports et commandes d’exploitation. `infrastructure/` fournit conteneurs et templates de déploiement. `docs/` documente architecture, installation, exploitation, utilisateur et écarts de conformité.

## Interface : Atelier documentaire

**Mouvement** : modernisme suisse, instrument de travail institutionnel. **Principes** : preuves avant scores, comparaison avant approbation, densité maîtrisée, distinction nette des états. **Palette** : bleu nuit et blanc cassé pour la stabilité, bleu pétrole pour les actions, ambre pour les revues requises, rouge réservé aux blocages. **Structure** : rail latéral fixe et plan de travail horizontal ; revue côte à côte source/traduction/diff, sans page marketing. **Motifs** : indicateurs d’étapes et filets fins, cartouches de provenance, panneaux de preuve. **Interactions** : commandes explicites et réversibles ; confirmation d’approbation avec attestation de revue, jamais masquer une erreur. **Animation** : transitions de 120–180 ms, aucune animation des documents, respecter reduced-motion. **Typographie** : Inter ou sans-serif système en interface, monospace système pour versions et identifiants, polices locales uniquement. **Marque** : « Atelier documentaire — comprendre, traduire, vérifier » ; rigoureux, calme, transparent. **Voix** : « Traduction à vérifier » ; « Aucune référence validée : qualité linguistique non mesurée ». **Logotype** : monogramme AD avec deux feuilles décalées, réalisé comme élément d’interface typographique. **Couleur signature** : bleu pétrole #096b78. Aucune illustration ni ressource distante nécessaire.

## Conditions de livraison et honnêteté

Livrer un socle exécutable et testé, plus les résultats exacts des commandes. Les critères industriels non vérifiables ici (Qwen privé, calibration humaine, GPU, charge 100 utilisateurs/200 pages, installation effective Kubernetes et validation bancaire) restent ouverts avec leur procédure. Ne jamais annoncer l’ensemble du cahier des charges « terminé » sur la seule base de tests techniques.
