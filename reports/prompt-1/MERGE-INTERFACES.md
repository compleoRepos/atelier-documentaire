# Contrat de merge — Prompt 1 / Prompt 2

Branche propriétaire : `feature/prompt-1-industrialisation-20261008`. Base : `6fb913a3a402e45c5813bf343fb85f26ef0e0e20`. Aucun merge ni modification de `main` par cette exécution.

## À conserver au merge

1. `backend/app/documents/preprocessing.py` : pipeline local sur copies, profils et sélection OCR. Le **renderer doit toujours reconstruire à partir de l’original**, jamais à partir de l’image nettoyée.
2. `analyze_document(source_path, work_dir, options)` et `translate_document(ir, work_dir, options)` conservent leurs signatures. Le preprocessing est appelé dans l’ingestion, pas dans la reconstruction.
3. Chaque page analysée par OCR contient `preprocessing`, `processing_image_path`, `protected_visual_regions`; l’IR porte également la liste consolidée de régions.
4. `preprocessing.transform_processing_to_source` et son inverse sont des matrices homogènes **3×3** composant toutes les opérations. Pour PDF, « source » signifie coordonnées de la page en points ; pour image/TIFF, pixels originaux. Les matrices auxiliaires suffixées `_pixels` restent en pixels du raster source. `source_coordinate_size` indique la taille dans l’unité source. Les bbox OCR, tables/cellules et régions sont déjà ramenées dans ces coordonnées ; **ne pas appliquer la transformation une seconde fois**.
5. `source_pixel_sha256` identifie les pixels rasterisés, pas le fichier original. L’empreinte du fichier original est `versions.source_sha256`, puis `source_sha256` du job. Aucune confusion entre ces deux empreintes n’est autorisée.
6. `protected_visual_regions` contient des **candidats**, sans authentification et sans garantie d’exhaustivité. Champs : `type`, `subtype`, `page`, `bbox`, `candidate`, `authenticated:false`, `detector`, `confidence:null` quand non calibrée. Les blocs intersectant ces zones sont marqués `protected`. Conserver les pixels source et bloquer une reconstruction qui les efface ; le reviewer peut compléter les zones.
7. `preprocessing.PreprocessingQualityScore` : `confidence_before`, `confidence_after`, `improvement`, `metric:"ocr_confidence_proxy"`, `cer:null`, `wer:null`, `validated:false`. Ne jamais réutiliser ce proxy comme taux d’exactitude OCR ou score de fidélité documentaire.
8. Télémétrie : version, profil, opérations, variantes rejetées, tailles, matrices, `ocr_before`/`ocr_after` (moteur, version, langues, blocs, caractères, confiance), durée. Les chemins locaux deviennent des URI `storage://` via les workers, y compris dans `preprocessing`.
9. Preview : `enhanced-NNN.png` est la copie de traitement sélectionnée, **éventuellement identique à l’original**. `/preview/enhanced/{page}?version=N` utilise un snapshot de cette version, pas la dernière analyse. La requête est authentifiée et isolée par tenant. Une correction copie l’image de sa version parent, sans repli vers une analyse plus récente.
10. `raster_adapter.raster_pdf_copy` est un **adaptateur d’ingestion TIFF multipage**, non une reconstruction concurrente. Il incorpore les pixels RGB de chaque frame, sans OCR ni traduction, dans une copie PDF aux dimensions exprimées en pixels source. Trois points d’entrée de `pipeline.py` et la preview de revue l’utilisent pour rendre les TIFF compatibles avec le renderer PDF existant. Conserver ces raccords lors du remplacement des fonctions de reconstruction par la branche 2. Aucun changement de `render_metrics.py` ou de l’algorithme DOCX/runs/tableaux n’a été réalisé ici.

## Zones de conflit prévisibles

- `pipeline.py` : prendre le nouveau `SUPPORTED`, les limites de rendu, `_tables` (adaptation raster → coordonnées source), `_analyze_image`, `analyze_document` de Prompt 1 ; prendre les reconstructions/runs/mesures de Prompt 2, en conservant le raccord TIFF et le refus de fallback offline après un échec privé.
- `jobs.py`, `routes.py` : conserver snapshots enhanced, URI et audit preprocessing ; fusionner les contrôles de revue supplémentaires de Prompt 2.
- `models.ts` : union des champs IR/qualité, sans perdre `PreprocessingQualityScore`.
- `review.page.ts` : conserver le quatrième panneau enhanced et ses ObjectURL ; prendre les améliorations de fidélité de Prompt 2.

## Conditions de qualification restant extérieures au code

Endpoint et tokenizer privés Qwen réellement provisionnés, modèles Paddle/embedding locaux le cas échéant, transcriptions et traductions humaines approuvées, baseline Golden humaine, revue exhaustive des signatures/cachets. Les tests avec doubles tokenizer ne qualifient pas un modèle Qwen réel.

## Ajout Interim explicitement arbitré par le coordinateur

- Conserver `interim.py` + `interim_guard.py`, routage explicite `engine=interim` de `service.py`, options serveur de `settings.py`/`jobs.py`, union providers/models Angular et avertissement hors Private Cloud de la fiche documentaire.
- Interim DEV/TEST = `gpt-5-mini`/tiktoken o200k_base. Entrée complète ≤22000, **max_completion_tokens TOTAL** ≤8000, marge2768 : plafond applicatif32768. Garder le contrat officiel et le circuit de budget/calibration ; ne pas restaurer le blocage provisoire par défaut pour manque de preuve au catalogue, ni réintroduire `max_tokens` dans la requête.
- Production/private refuse ce provider. Réels8SHA denylistés ; fixture autorisée + allowlist SHA du payload/contexte avant réseau. Le job inclut `source_sha256`, scope et options serveur ; ne pas contourner le gate ou récupérer des textes/mémoires réels à partir d’une fixture.
- Garder provider demandé/réel, modèle servi, usage réel/raisonnement et référence humaine=false dans la telemetry/audit. L’étape UI traduction est **failed** pour un problème Interim critique même si un IR/candidat conservant la source existe. Aucune copie de source préservée après erreur n’est présentée comme traduction modèle réussie.
- Décision définitive : **8 documents réels = NOT_EXECUTED pour traduction modèle par confidentialité**, Qwen privé NOT_AVAILABLE_IN_ENVIRONMENT ; seul le pipeline OCR/reconstruction locale offline du corpus a été exécuté. Interim live uniquement fixture codée non personnelle, preuves dans INTERIM-TRANSITION.md.
- Code final testé : `b7e40a0223d6db00af494427a542ba8646be080a` ; CI37760420819 success, private-acceptance/manual-release-gate skipped. Les XML/code/probes sont présents dans le sandbox autorisé, aucun original/IR privé n’est dans Git.
