# Industrialisation — contrat de travail et d’intégration

## Contraintes immuables

- Racine Git autonome : dépôt privé `compleoRepos/atelier-documentaire-prive`, branche `main`.
- Chaque lot validé est commité et poussé par le coordinateur. Auteur ET committer : **Hamza NORDINE** ; adresse noreply du compte authentifié. Aucun agent secondaire ne commit/push.
- Aucun original, texte extrait, résultat privé, référence réelle, poids ou secret dans Git. Données privées de test hors Git, dans un espace privé dont le chemin n’est pas publié.
- Pas d’OpenAI/Interim proxy/Google/Azure/DeepL ou autre modèle public pour les documents. Aucun téléchargement de poids implicite en runtime. Pas de déploiement PROD ni de modification des accès/secrets bancaires.
- Les scores sont calculés par une méthode documentée, avec provenance et couverture. Aucune constante PASS/100%, approximation géométrique présentée comme sémantique, ni confiance OCR présentée comme exactitude.

## Contrat qualité

Module à créer : `app.ai.quality.engine`.

```python
def evaluate_quality(ir: dict, translations: dict[str,str], render_result: dict | None = None,
                     reference: dict | None = None, options: dict | None = None) -> dict:
    ...
```

Retour : dictionnaire des métriques `ocr_score`, `translation_score`, `semantic_score`, `layout_score`, `visual_score` (échelle 0..1 ou `None` si une preuve nécessaire est absente), `status`, `issues`, `critical_entity_errors`, `hallucination_errors`, `reference_status`, `provenance`, `coverage`. Les scorers doivent distinguer exactitude contre référence, défaut mesuré et mesure absente. Une valeur n’est jamais fabriquée faute de poids/endpoint/référence.

`render_result` possède les chemins des previews, métriques de géométrie/structure, état de reconstruction ; la qualité visuelle doit comparer hors zones textuelles réellement remplacées et régions protégées. Il faut aussi détecter régressions de texte/bords/layout ; masquer toute une page n’est pas valide.

Les dates/montants/noms/sociétés/codes/IBAN/téléphones/emails/adresses explicitement protégés sont comparés en occurrences. Les segments numériques/identifiants/noms seuls ne sont pas automatiquement marqués non traduits. Les détecteurs automatiques déclarent leur couverture/limites.

## Répartition exclusive

1. Qualité : `backend/app/ai/quality/*`, `backend/app/ai/vision/*`, tests `test_quality_v2*`, `test_entities_v2*`, `test_visual_v2*`, `docs/quality-methods.md`. Pas de modification de pipeline/API/settings/deps.
2. Documents : `backend/app/documents/*`, `backend/app/domain/classification.py`, `backend/app/ai/ocr/*`, tests `test_document_v2*`, `test_ocr_v2*`, `docs/document-engine-v2.md`. Brancher le contrat qualité sans modifier ses fichiers ; préserver compatibilité des anciennes routes/tests.
3. Exploitation : `infrastructure/*`, Dockerfiles, `.dockerignore`, Compose, CI GitHub/GitLab, nouveaux `tools/ops_*`, `tools/release_gate.py`, tests `test_ops_v2*`, docs exploitation/release. Pas de modification du backend, de requirements/package locks ou d’un cluster réel.
4. Coordinateur : API, models/settings/db/main, jobs/workers, migrations, observabilité, frontend, rapports/Golden/baseline, dependencies et intégration.

## Acceptation de ce lot

Achever et tester les composants logiciels indépendants de l’accès bancaire. Le code doit être capable de mesurer les métriques dès que leurs entrées réelles sont présentes, au lieu de retourner `None` inconditionnellement. Les résultats sur les huit originaux restent séparés des tests synthétiques et ne deviennent pas des références humaines par assertion. La recette banque/Qwen/GPU reste une étape explicite, pas une réussite supposée.
