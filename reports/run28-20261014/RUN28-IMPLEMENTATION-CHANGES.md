# RUN28 — Modifications d’implémentation

Base : `feature/run27-score-remediation-20261013` @ `54bf5f2` (tête RUN27). Branche : `feature/run28-moteur-simplification-20261014`. Les commits et leurs empreintes figurent dans RUN28-REGRESSION-RESULTS.

## 1. Inventaire des fichiers

Diff depuis `54bf5f2` (fichiers existants) : 19 fichiers, +990 / −51 lignes. Nouveaux fichiers : 8 (2 345 lignes, dont 1 301 de tests backend et 219 de tests frontend).

| Fichier | Nature | Objet |
| --- | --- | --- |
| `backend/app/documents/language_evidence.py` | modifié (+224) | F35 `reference_line` (deux niveaux stricts), F39 détection de recopie partielle |
| `backend/app/ai/translation/service.py` | modifié (+180) | filtre F35 avant envoi (`REFERENCE_LINE_KEPT`, `NOT_SENT`), reprise F39, reprise ordinale bornée F41 (`TARGET_ORDINAL_RETRY`, `GUARD_RETRY_EXHAUSTED`), provenance `retry_kind` |
| `backend/app/documents/block_status.py` | modifié (+15) | statuts explicites : `reference_line`, `reference_returned_unchanged`, `partial_translation`, `render_office_target_missing`, `render_office_unexpected_change` |
| `backend/app/documents/pdf_fidelity.py` | modifié (+121) | F37 repli condensé, F38 filets inclinés, F38b couleur papier robuste |
| `backend/app/ai/translation/typography.py` | modifié (+7) | F40 neutralisation des contrôles bidi dans la clé typographique |
| `backend/app/ai/quality/entities.py` | modifié (+14) | F42 nombres et jours ordinaux |
| `backend/app/documents/pipeline.py` | modifié (+279) | routage XLSX/PPTX (`OFFICE_FORMATS`, `_office_ir`, `_reconstruct_office`), vérification native, F40 `_normalise_typography_only` |
| `backend/app/documents/ooxml_office.py` | **nouveau** (544) | parcours natif XLSX/PPTX : collecte, édition ciblée du paquet, vérification structurelle |
| `backend/app/infrastructure/validation.py` | modifié (+41/−15) | validation OOXML généralisée (`_validate_ooxml`) |
| `backend/app/api/routes.py`, `backend/app/application/jobs.py` | modifiés (+6/−2, +3/−1) | aperçus et livraison des formats Office |
| `tools/interim_owner_corpus_run.py` | modifié (+46) | invalidations mémoire F35/F39/F41, refus confirmés réutilisés sans renvoi |
| `backend/Dockerfile` | modifié | `libreoffice-calc`, `libreoffice-impress` (aperçus XLSX/PPTX) |
| `.github/workflows/ci.yml` | modifié | `fonts-dejavu-extra` sur les deux lignes `apt` (sinon tests F37 ignorés) |
| `frontend/src/app/core/indicators.ts` | **nouveau** (281) | calcul pur des six indicateurs de contrôle |
| `frontend/src/app/pages/document-detail.page.ts`, `frontend/src/styles.css` | modifiés (+22, +26) | panneau « Synthèse de contrôle » |
| `frontend/src/app/pages/review.page.ts`, `upload.page.ts` | modifiés (+14, +10/−4) | dépôt XLSX/PPTX, avertissement « aucune preuve visuelle » |
| `backend/tests/unit/test_run28_regressions.py` | **nouveau** (32 tests) | F35, F39, mémoire et service |
| `backend/tests/unit/test_run28_render_regressions.py` | **nouveau** (15 tests) | F37, F38, F38b, F40 |
| `backend/tests/unit/test_run28_office.py` | **nouveau** (22 tests) | XLSX/PPTX : collecte, intégrité, falsifications, dépôt, pipeline |
| `backend/tests/unit/test_run28_ordinal_retry.py` | **nouveau** (14 tests) | F41, F42 |
| `backend/tests/unit/test_run18_regressions.py` | modifié (+2) | attente stricte mise à jour avec la clé additive F41 `refusal_reused_not_resent` (égalité stricte conservée) |
| `frontend/src/app/core/indicators.spec.ts`, `pages/document-detail.run28.spec.ts`, `pages/review.page.spec.ts` | 2 nouveaux, 1 modifié (+14 tests) | indicateurs, rendu DOM du panneau, avertissement Office |

Formatage : tous les fichiers nouveaux et modifiés déjà formatés passent `ruff format --check`. Trois fichiers ne l’étaient **pas déjà** à `54bf5f2` (`routes.py`, `jobs.py`, `validation.py`, contrôle rejoué sur la version RUN27). Ils n’ont pas été reformatés globalement, pour garder un diff lisible.

**Aucune formule, aucun poids ni aucune règle de score n’a été modifié** (`tools/recette` inchangé depuis `54bf5f2`, gels v1 et v2 revérifiés).

## 2. Parcours A — documents éditables (XLSX, PPTX)

- **Collecte** : chaînes partagées réellement utilisées et `inlineStr` (XLSX) ; paragraphes `a:p` des diapositives, segments séparés par `a:br`, champs `a:fld` exclus (PPTX). Les formules, noms de feuilles, commentaires, notes et graphiques ne sont pas collectés.
- **Édition** : seuls les nœuds texte ciblés sont réécrits. Toutes les autres parties du paquet sont copiées octet pour octet. Aucune conversion en PDF.
- **Vérification native** (sur le fichier produit) : cibles présentes, aucun autre texte modifié (instantané canonique, texte neutralisé uniquement dans les parties réécrites), formules, noms de feuilles et unités identiques. Résultat : `native_verification=VERIFIED`, distinct de `visual_proof=NOT_AVAILABLE`.
- **Alertes** : `OFFICE_TARGET_NOT_APPLIED`, `OFFICE_UNEXPECTED_TEXT_CHANGE`, `OFFICE_PACKAGE_INTEGRITY_FAILED` (critiques, bloc `FAILED`), `PPTX_TEXT_MAY_OVERFLOW` (estimation), `OFFICE_VISUAL_PROOF_UNAVAILABLE`, `XLSX_HEADER_FOOTER_NOT_TRANSLATED`.
- **Dépôt** : mêmes garde-fous que DOCX, plus refus des macros, d’ActiveX, des liens externes (`xl/externalLinks`), des connexions et des objets incorporés, et refus si la partie principale manque.
- **Interopérabilité** (fichiers synthétiques produits par LibreOffice) : collecte 7 blocs (XLSX) et 2 (PPTX), tous appliqués, `VERIFIED`, réouverture LibreOffice rc = 0. Limites constatées : rognage de cellules XLSX non détecté (OI-08), conversion d’aperçu d’un PPTX minimal sans masque en échec explicite `OFFICE_LIBREOFFICE_CONVERSION_FAILED` (OI-09).

## 3. Parcours B — documents scannés

F37, F38, F38b et F40 (détails dans RUN28-ROOT-CAUSES). L’image originale reste la référence immuable. Les régions protégées et la garde d’encre résiduelle ne sont pas assouplies : quand un filet conservé laisse l’encre source exposée, la ligne reste dans sa langue d’origine et la page n’est pas maquillée.

## 4. Traduction

- **Lignes de références** (F35) : conservées sans envoi, provenance `NOT_SENT`, statut explicite.
- **Traductions incomplètes** (F39) : une reprise dédiée. En cas d’échec, source conservée et échec visible.
- **Reprise ciblée bornée** (F41) : une seule reprise par garde ordinale, puis refus versionné réutilisé, sans boucle d’envoi.
- **Mémoire de traduction** : chaque correspondance est revalidée contre les gardes courantes. Invalidations tracées : `not_sent_by_current_service`, `partial_source_copy`, `previous_guard_rejection`. Les refus confirmés sont réutilisés (`refusal_reused_not_resent`).
- **Provenance** par bloc : `TRANSLATION_MEMORY`, `MODEL_CALL` (avec `retry_kind`), `NOT_SENT`, origine d’origine conservée (`cached_origin`).

## 5. Interface

Panneau « Synthèse de contrôle » (six indicateurs, calcul pur dans `core/indicators.ts`) :

1. couverture mesurée (plancher 0,1 %, inconnu = « Non mesuré ») ;
2. erreurs critiques (dédoublonnées document + traduction, codes principaux) ;
3. reconstruction (`FAILED:render_*`, vérification native ; Office `VERIFIED` sans preuve visuelle = avertissement) ;
4. revue humaine (`FAILED` + `UNCERTAIN` + non traités ; mention « vérification automatique ≠ validation humaine ») ;
5. provenance (fournisseur, origines par bloc, requêtes, mode) ;
6. statut global (un statut approuvé avec des erreurs critiques reste en avertissement, avec la mention « malgré »).

## 6. Moteur privé Qwen / vLLM

Aucune modification de code en RUN28. L’audit de `PrivateQwenEngine` confirme : URL privée et liste d’hôtes, DNS revalidé avant connexion, redirections refusées, `trust_env=False`, tokenizer local obligatoire, plafond de 32 768 tokens, sortie ≤ 8 000, marge, contrôle préalable du gabarit complet (`CONTEXT_OVERFLOW` avant tout appel HTTP), `finish_reason` et JSON stricts, provenance (`served_model`, `usage`, empreinte du tokenizer). Le moteur est choisi explicitement (`offline`, `private`, `interim`), **sans repli** (tests existants). **Aucun endpoint, tokenizer ou poids réel n’était disponible : Qwen n’est pas qualifié** (OI-10).

## 7. Expurgation de confidentialité (commit séparé `c973e73`)

Ce commit ne contient aucun changement fonctionnel. Il porte sur 15 fichiers :

- 2 fichiers de code (`entities.py`, `service.py`) : commentaires seulement, AST identique ;
- 10 fichiers de tests hérités : littéraux remplacés par des textes inventés, de même longueur quand la géométrie en dépend, assertions inchangées ;
- 2 rapports `final-20261009` et 1 document `docs/` : citations remplacées par des descriptions.

Les commentaires RUN28 de `language_evidence.py` et `service.py` ont été corrigés de la même manière dans le commit `d189972`. Détails et limites : RUN28-REGRESSION-RESULTS § 7 et RUN28-OPEN-ISSUES, OI-16.
