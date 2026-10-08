# Suivi des résultats — critères du cahier des charges

Le cahier des charges intégral est conservé dans `docs/requirements.txt`. Les états ci-dessous doivent rester conformes aux preuves, pas aux intentions.

- [x] Analyse initiale : inventaire des 8 originaux, format, taille, pages, langues, type, domaine, scan/natif, tableaux/images/signatures/cachets/formulaires, complexité ; matrices et cas difficiles. Observations, mesures et inconnus séparés.
- [x] Document catalog JSON et cas TC-DOC-001 à TC-DOC-008, Golden Input distinct du Golden Expected et des Golden Metrics. Aucune référence validée inventée.
- [ ] Pipeline document structuré : ingestion -> document understanding -> OCR/layout -> structural representation -> contextual translation -> terminology/memory -> QC -> reconstruction -> visual validation -> human review -> final. PDF/DOCX/JPG/PNG V1 ; architecture extensible V2 XLSX/PPTX/TIFF.
- [ ] OCR et intelligence : détection de langues multilingues, employment certificate/bank statement/contract/invoice/diploma/administrative form, paragraph/title/table/image/signature/stamp/checkbox/header/footer ; CER/WER, nombres, dates, noms et références comparés au texte validé humainement.
- [ ] Traduction : français naturel professionnel contextualisé, fidélité/cohérence/terminologie/style/absence d’hallucination ; domaines HR/BANKING/LEGAL/FINANCE/ADMINISTRATION/ACADEMIC ; tests de termes ambigus, pas uniquement BLEU.
- [ ] Entités : noms/prénoms/sociétés/dates/montants/références/numéros/IBAN/téléphones/emails/adresses inchangés ; information ajoutée/retirée/modifiée détectée ; chiffres et identifiants sous contrôle renforcé ; date modifiée = FAIL CRITICAL.
- [ ] Qwen privé : TranslationEngine interchangeable, MAX_CONTEXT <=32768, TARGET_INPUT 22000, MAX_OUTPUT 8000, SAFETY_MARGIN 2768 configurables ; aucune requête ne dépasse 32K ; tokenizer et enveloppe complète contrôlés ; aucun basculement public.
- [ ] Chunking sémantique pages/sections/paragraphes/tableaux/phrases/blocs logiques ; ne jamais couper arbitrairement une structure ; ContextPackBuilder budgeté avec global/relevant terminology/entities/memory/previous/current ; document/terminology/entity/translation/decision memories, jamais toute la mémoire.
- [ ] Terminologie : glossaire par client, priorité client configurable ; mémoire de traduction réutilisable uniquement après validation humaine.
- [ ] Reconstruction Python à partir de traduction structurée, pas PDF généré par le modèle ; mêmes pages/dimensions/blocs/tableaux/images/signatures/cachets/en-têtes/pieds/pagination. Comparaison tableaux lignes/colonnes/cellules/fusions/en-têtes/ordre/structure. Débordements/chevauchements/disparitions/coupures signalés.
- [ ] Document diff original/traduction/diff, images QA conservées et score visuel défini sans confondre variation linguistique et régression graphique. Régression baseline mesurée et déploiement bloqué si baisse.
- [ ] Seuils configurables OCR>=95%, translation>=90%, semantic>=95%, layout>=90%, visual>=90%, erreurs entités critiques=0, hallucinations=0, context overflow=0 ; métriques absentes ne deviennent jamais des réussites.
- [ ] Human review : REVIEW_REQUIRED sous seuil ou incertitude ; corriger/valider/rejeter/terme/glossaire/mémoire ; Golden Reference via validation humaine explicite versionnée et auditée, puis dataset régression. Aucune approbation automatique.
- [ ] Backend FastAPI/Pydantic/SQLAlchemy Python3.12+, OCR privé, PostgreSQL, S3 compatible, Celery/Redis ; observabilité et workers. Documents/version original/IR/traduction/final et versions modèle/OCR/prompt/glossaire/mémoire conservés.
- [ ] Angular TypeScript : /login /dashboard /documents /upload /documents/:id /review/:id /glossary /translation-memory /admin /testing /audit ; QA dashboard documents/tests passed/failed/translation/OCR/layout/semantic/visual/critical errors réels.
- [ ] Sécurité : fichiers malveillants/extensions/MIME spoofing/taille/cross-tenant/non autorisé/injection documentaire/prompt injection/extraction données ; document non fiable strictement séparé des instructions ; aucune donnée à OpenAI/Google Translate/Azure Translator/DeepL public. Accès aux fichiers audité et limité au tenant.
- [ ] Audit user/document/timestamp/model/model version/prompt/glossary/memory/result/quality/reviewer sans texte personnel dans journaux ; action Golden versionnée.
- [ ] `pytest`, `pytest tests/golden_dataset` traitant automatiquement tout dossier ; unit/token/chunk/context/terminology/entity/render, intégration OCR/Qwen/PostgreSQL/storage/queue, E2E upload->analyze->translate->reconstruct->validate->download, Golden/régression/visuel/sécurité.
- [ ] Tests charge 1/10/50/100 utilisateurs et 1/10/50/100/200 pages ; temps total/OCR/LLM/GPU/mémoire/queue/throughput mesurés, pas simplement scripts fournis.
- [ ] Dockerfiles/Compose, Kubernetes/Helm effectif ; CI lint/unit/security/integration/Golden/visual/performance/build/DEV/acceptance/TEST/approval/PROD. Déploiement PROD protégé et non effectué dans cette tâche.
- [ ] Documentation architecture/installation/exploitation/utilisateur/OpenAPI et rapport de qualité vérifié ; code complet livré sans modifier l’application BTP.
- [ ] Validation finale indépendante de l’implémentation et correction des défauts confirmés.

## Dépendances d’acceptation industrielle

Endpoint privé Qwen, tokenizer et poids locaux, calibration PaddleOCR, références OCR/traductions humaines, protection/annotations signatures et cachets, environnement bancaire/TLS/secrets, GPU et cluster Kubernetes ne sont pas fournis. Les tests unitaires et hors ligne ne prouvent pas les critères linguistiques ou la readiness bancaire.
