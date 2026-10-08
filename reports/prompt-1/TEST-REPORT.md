# Tests exécutés — Prompt 1

Commit de code : `b7e40a0223d6db00af494427a542ba8646be080a`. Aucun appel Qwen réel ni référence humaine fabriquée ; Interim seulement sur synthétique explicitement autorisé. Les valeurs ci-dessous viennent des sorties de commandes et XML locaux, pas d’une estimation.

| Ensemble définitif | Réussis | Échecs | Portée |
|---|---:|---:|---|
| Python technique complet | 294 | 0 | unitaires, intégration, E2E, non-régression, sécurité |
| Corpus privé technique | 8 | 0 | les 8 PDF/31 pages, OCR local et reconstruction offline |
| Angular | 16 | 0 | auth, formatters, review, enhanced et vrai score preprocessing |
| Géométrie + régressions ciblées | 39 | 0 | sous-ensemble déjà compté dans Python, non additionné |

**Total de tests uniques définitifs : 318 réussis, 0 échec** (294 Python techniques + 8 corpus + 16 Angular). Les multiples replays ciblés ne gonflent pas ce nombre. La réussite corpus est un résultat technique, pas un PASS Golden humain. Les sondes/scripts live ne sont pas ajoutés aux comptes pytest : JSON/entités/glossaire sur3blocs synthétiques passent ; caps16/64 et données de calibration dans INTERIM-TRANSITION.md.

## Commandes et outils

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security -q
OMP_THREAD_LIMIT=2 OPENBLAS_NUM_THREADS=1 PYTHONPATH=backend .venv/bin/pytest backend/tests/golden_dataset -q
.venv/bin/ruff check backend tools
.venv/bin/python -m compileall -q backend/app tools
cd frontend && npm run typecheck && npm test && npm run build && npm audit --audit-level=high
cd .. && .venv/bin/pip-audit -r backend/requirements.txt --strict
```

Ruff/compileall/typecheck/build réussis. `npm audit` : 0 vulnérabilité ; `pip-audit --strict` : aucune vulnérabilité connue trouvée. Avertissements non bloquants : PyMuPDF API fitz deprecated, Pillow getdata deprecated, Alembic path_separator et Angular NG8107 préexistant. Ce ne sont pas des erreurs de test.

## CI effectivement observée

[Run 37760420819](https://github.com/compleoRepos/atelier-documentaire-prive/actions/runs/37760420819) — état `completed`, conclusion `success` sur `b7e40a0223d6db00af494427a542ba8646be080a`.

| Job | Conclusion |
|---|---|
| backend | success |
| frontend | success |
| backend-integration-and-migrations | success |
| container-and-manifest-validation | success |
| private-acceptance | skipped |
| manual-release-gate | skipped |

Les jobs private-acceptance/manual-release-gate ne sont pas activés par un push de branche ; ils n’ont pas été contournés. Le sandbox ne dispose pas de Docker, les validations conteneurs exécutées sont celles de la CI, si le job l’indique comme réussi.

## Corrections et exécutions intermédiaires

- Baseline locale avant changement : 167 Python techniques réussis ; baseline communiquée : 12 Angular.
- Premier intermédiaire : 212 réussis / 1 échec (ancienne attente de mémoire non validée). Attente adaptée au contrat : seuls validated:true sont repris, et le rejet false est asserté.
- OCR incliné : test corrigé pour une confiance initiale null, jamais convertie en zéro artificiel.
- Ancienne attente d’un dictionnaire versions exact : étendue aux nouveaux champs de provenance, pas supprimée.
- Corpus : attente historique not_evaluated élargie à not_available, les deux signifiant réellement absence de référence ; translation_score reste null et REVIEW_REQUIRED obligatoire.
- Première suite mixte technique/corpus interrompue (code 137), non utilisée comme preuve finale. Rejouée en ensembles distincts avec corpus après le banc lourd et threads bornés. Aucun résultat manquant n’est compté comme PASS.
- Derniers garde-fous anti-perte des marques pâles/canvas perspective : 39 tests géométriques ciblés réussis ; CI et passage corpus final sur le commit de code les incluent.

## Non disponible, non qualifié

Qwen/tokenizer réels 32K, CER/WER corpus et qualité de traduction humaine : NOT_AVAILABLE_IN_ENVIRONMENT. Les tests budgets 10K/20K/22K/25K/30K/31K/32K/32K+ utilisent un double local déterministe avec comptage rendu, schéma, sortie et marge. Ils ne valident pas le modèle privé réel. Les tables atomiques, finish_reason, placeholders, contexte borné et absence de fallback sont testés.

Traduction modèle des8originaux = NOT_EXECUTED par décision utilisateur (confidentialité) ; leurs8SHA réels refusésavant réseau. Qwen privé = NOT_AVAILABLE_IN_ENVIRONMENT. Interim = providerdistinct/gpt-5-mini, contrat max_completion_tokens TOTAL≤8000 + entrée≤22000 + marge2768≤32768, circuitouvert en violation, jamaisfallback. Voir INTERIM-TRANSITION.md. Les XML/logs techniques sont dans test-report/prompt-1/, ignorés par Git ; les originaux/IR/previews confidentiels n’ont pas été publiés.

Les annotations détaillées GitHub n’ont pas été récupérées (`checks:read` refusé HTTP403). Aucune extension de permissions n’a été demandée ; statut, conclusion, SHA et étapes des jobs ont été obtenus via les endpoints Actions autorisés. Les codes ANSI du JSON CLI forcé en couleur ont été retirés avant parsing, sans modifier les valeurs. Cette limite ne transforme pas les gates privés skipped en PASS.
