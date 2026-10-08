# Industrialisation logicielle v2 — état vérifié

## Verdict

Le socle a été durci et testé au-delà du prototype initial. Il ne faut pas confondre **logiciel avec contrôles de production** et **service bancaire qualifié sur son infrastructure et son modèle**. La promotion PROD n’a pas été effectuée.

## Changements réellement implémentés

- **Sécurité et sessions** : sessions HttpOnly, protection CSRF, révocation persistante, isolation d’un uploader y compris au sein du même tenant ; Angular ne conserve plus le JWT dans localStorage. Validation PDF/DOCX renforcée contre actions embarquées, macros et relations externes. Antivirus ClamAV privé en streaming, fail-closed lorsque requis.
- **Production** : configuration bloquante si les prérequis privés, secrets, sessions sûres, antivirus ou migrations manquent ; API et worker vérifient le schéma Alembic. Production ne crée pas implicitement ses tables.
- **Données et observabilité** : migrations Alembic réversibles ; snapshots IR figés par version/SHA ; temps des stages et mesures HTTP/stages Prometheus sans données personnelles dans les labels ; readiness réelle PostgreSQL/S3/Redis ; timeouts Celery et S3 ; classe d’exception seulement dans les logs.
- **Traduction privée** : Qwen interchangeable, budget complet des requêtes/chat template/sortie/marge sous 32 768 tokens, tokenizer local, contexte et mémoires pertinents, DNS/allowlist privés et absence de redirection/fallback public.
- **Qualité** : CER/WER comparés seulement à une transcription OCR humaine explicitement liée au SHA ; rubriques humaines liées à la traduction relue ; providers concrets d’encodage sémantique local et de juge Qwen privé, sans téléchargement automatique. Provenance, couverture et contradictions conservées ; les métriques absentes ne deviennent pas des scores de réussite.
- **Documents** : détection géométrique candidate des scans (tableaux, cellules/fusions, formulaires, checkboxes), sans inventer leur validation ; reconstruction PDF/DOCX ; pagination DOCX physique par LibreOffice ; comparaison du candidat réellement rendu, extraction PDF indépendante, images/diff et crops de régions protégées. Le changement de longueur linguistique n’est pas assimilé automatiquement à un déplacement de cadre.
- **Exploitation** : scripts de sauvegarde/restauration PostgreSQL et S3 avec hashes et destinations isolées, refus d’écrasement ; chart Helm, images non root et gate de release bloquante sans preuves privées, baseline et approbation.

## Preuves locales exécutées

| Vérification | Résultat | Périmètre |
| --- | --- | --- |
| Python unitaires, intégration, E2E, régression, sécurité | **167 réussis** | Suite finale, incluant le correctif de performance raster et son test adversarial |
| Angular | **12 réussis**, typecheck et build réussis | Sessions, CSRF, revue et rechargement de versions |
| Dépendances Python | Aucune vulnérabilité connue détectée | `pip-audit --strict` sur requirements |
| Dépendances npm | **0 vulnérabilité connue** | `npm audit` |
| Helm / Compose | Validés | Lint et configuration, pas un déploiement Kubernetes bancaire |
| Migrations | Exécutées sur PostgreSQL du stack v2 | Démarrage avec `AUTO_CREATE_SCHEMA=false` |
| Stack Docker v2 | **14 contrôles HTTP réussis** | Upload synthétique français → Celery → PostgreSQL/S3 → reconstruction → previews → revue → Golden → téléchargement |
| Sauvegarde/restauration | **2 documents, 16 objets S3**, hashes vérifiés | Base et bucket de quarantaine neufs, uniquement données synthétiques |
| Corpus original | **8/8 traitements techniques, 31 pages** | Tous `REVIEW_REQUIRED`, aucune référence humaine présumée ; recette linguistique `NOT_EVALUATED` |

Le détecteur raster a été profilé puis corrigé : index spatial et bornes explicites sur grilles/rectangles avec incertitude déclarée plutôt que troncature cachée. Le test 800×1200 à nombreux traits avec tableau et checkbox prend 0,0752 s dans le laboratoire. Ce chiffre concerne seulement le détecteur, pas l’OCR ni la traduction complète. La campagne des 31 pages reste une campagne CPU hors ligne ; elle ne prouve pas un SLA bancaire.

Les scores géométriques/pixel locaux à 1 sur ces candidats offline mesurent ici la conservation d’artefacts essentiellement inchangés. **Ils ne démontrent pas la mise en page d’une traduction Qwen réelle**. Le résumé conserve les moyennes de recette à `null` faute de références validées. Pour PDF/scans, les tableaux restent des candidats : la comparaison indépendante exhaustive des cellules/fusions du candidat n’est pas certifiée. Les styles DOCX multi-runs et l’identité/authenticité des signatures/cachets non annotés restent explicitement non vérifiés.

Le sandbox comportait à la fois des filtres iptables legacy/nft : une règle **intra-bridge v2 uniquement** a été nécessaire au laboratoire. Cela ne constitue pas une ouverture des services de données sur Internet et ne doit pas être transféré aveuglément à l’infrastructure cible.

## Dépendances d’acceptation industrielle

1. **Qwen privé joignable**, tokenizer/poids locaux exacts et versions, capacité CPU/GPU cible. Aucun serveur ou accès privé n’a été fourni ; les tests offline ne certifient pas ses traductions.
2. **Références humaines validées** : transcription OCR, traduction française, annotations des entités/régions sensibles et rubriques de qualité pour les huit originaux. Aucune validation humaine n’est inventée.
3. **Calibration OCR, sémantique et visuelle** sur le corpus et sa baseline approuvée. Une similarité cosinus ou une image proche n’est pas une certification de fidélité juridique ni d’absence d’hallucination.
4. **Environnement banque** : TLS, coffre/KMS, antivirus privé, stockage/chiffrement, cluster et contrôles réseau, comptes/roles et approbation de mise en production.
5. **Recette sur cette infrastructure** : traductions Qwen réelles, charge avec OCR/LLM/GPU, tests adversariaux, restauration, critères et approbation de promotion. Les performances synthétiques locales ne sont pas extrapolées.

Le code et ses tests sont livrables ; ces éléments externes sont nécessaires pour établir une qualification industrielle, pas pour remplir artificiellement une case « PROD READY ».
