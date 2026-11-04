# LOT 2.3, Phase B : corrections, RAG UE et prise en charge des 24 langues de l’UE

**Dates :** 3 et 4 novembre 2026. **Auteur et committer de tous les commits :** Hamza NORDINE. **Branche :** `feature/lot23-phase-b-20261103`, construite sur `feature/lot23-qualification-20261102` (rapports de Phase A). **Dépôts :** les deux dépôts sont **privés** jusqu’à nouvel ordre. **Production : NO-GO**, inchangé.

## 0. Synthèse

**Consignes.** Le 3 novembre : « Corrige ce qu’il y a et constitue ton RAG depuis ce que tu trouves sur internet avec des dictionnaires de traduction de toutes les langues de l’Union européenne plus les lois du travail de l’UE ; push tout sur Git avec la base de contenu du RAG ; Git en privé jusqu’à l’ordre d’ouvrir en public ; évite toute dégradation de l’existant. » Puis, dans la nuit : « Fais tes propres décisions ; toutes les langues prises en charge, même dans le RAG ; un taux de confiance de 92 % au minimum, jugé par toi-même. » J’ai traité la première consigne comme la validation de la Phase A et l’autorisation de la Phase B, y compris pour les fichiers gelés, à condition de prouver la non-régression.

**Un défaut majeur trouvé et corrigé dans la nuit.** Le produit ne **reconnaissait que 7 langues** (anglais, français, allemand, italien, espagnol, néerlandais, arabe). Un document grec, polonais ou maltais était classé « langue inconnue ». Le RAG, qui cherche les termes dans les langues reconnues du document, ne pouvait donc **rien injecter** pour 18 des 24 langues de l’UE, quel que soit le contenu de sa base. Les tests du 3 novembre ne le montraient pas, car ils posaient la langue à la main. Le détecteur reconnaît désormais les 24 langues de l’UE et l’arabe, et le parcours complet est testé pour chaque langue.

**Ce qui est livré.**

- **Six corrections de l’audit et la levée de la limitation du RAG à 5 langues**, chacune avec des tests qui échouent sur le code d’origine : D-DET-02, D-ENG-01, D-OPS-01, F-L2-03, D-OCR-06 et D-PERF-TOK (§2).
- **Détection et classement des 24 langues de l’UE et de l’arabe**, sans aucun changement pour les 7 langues historiques (§9).
- **La base de contenu du RAG**, versionnée dans le dépôt (10,5 Mo) : EuroVoc 4.24 (20 537 lignes, 23 paires vers le français), 25 actes du droit du travail de l’UE en 24 langues (11 208 articles-langues), 1 654 définitions légales alignées, et une paire arabe → français de 290 lignes (§4).
- **Une évaluation automatique de l’exactitude du contenu** par deux modèles, et un indice de confiance pré-déclaré (§10).

**Indice de confiance : atteint, à mon jugement.** La plus faible borne basse à 95 % des composantes mesurées sur échantillon est de **93,3 %** (exactitude d’EuroVoc), au-dessus du seuil de 92 %. Toutes les autres composantes sont plus hautes. Trois sous-groupes restent sous le seuil et sont présentés comme limites : les fragments de moins de 60 caractères (86,4 %), l’irlandais (90,8 %) et le slovène (91,7 %). L’OCR Surya lit une page de chacune des 24 langues de l’UE avec un F1 d’au moins 0,95 (moyenne 0,994), et l’arabe à 0,945 (§9.4). Cet indice porte sur le périmètre livré. Il **ne mesure pas la qualité de traduction**, il ne remplace pas la relecture humaine, et il ne lève pas le NO-GO de production.

**Non-régression.** La suite backend complète donne **1 207 tests réussis, 2 ignorés, 0 échec** (175 tests de plus qu’en Phase A, aucun disparu). Golden 8/8, PostgreSQL 3/3, Compose et Helm sont OK. Sur 646 documents du corpus bancaire et 2 229 paragraphes officiels en langues historiques, la langue et le classement sont **identiques** à ceux du code d’origine. La CI reste rouge sur deux audits de dépendances (Pillow, outillage npm), dont les correctifs exigent des montées de version majeure (§7).

**Ce qui n’est pas fait.** Douze défauts de l’audit restent ouverts, dont deux critiques (D-REC-02, D-OPS-02) (§3). IATE n’est pas inclus (compte EU Login requis). Aucune ligne du RAG n’a été relue par un humain, et le gain sur la traduction n’est pas mesuré, faute de moteur cible.

## 1. Périmètre et règles appliquées

**Base.** La branche part du commit des rapports de Phase A, lui-même placé sur la branche Surya auditée. Elle compte 18 commits de code, de tests et de données, plus les commits de documentation et de rapport. Il n’y a ni fusion dans `main`, ni déploiement, ni démarrage du LOT 3.

**Règles.**

- Chaque correction a un test qui échoue sur le code d’origine, ce qui est vérifié en rejouant le test sur l’arbre d’origine.
- Aucun comportement par défaut n’est modifié quand le changement peut dégrader l’existant. Pour les langues, la règle est stricte : les 7 langues historiques doivent garder **exactement** la même décision.
- Le RAG reste `DISABLED` par défaut, sans base vectorielle, sans Qdrant ni BGE-M3.
- Rien n’est publié automatiquement dans le RAG.
- Les sources sont officielles ou sous licence ouverte vérifiée. Aucune aspiration ni contournement n’a été fait (IATE).
- Aucune donnée client n’a été manipulée. Les évaluateurs automatiques n’ont reçu que des données publiques.
- Les paramètres de détection ont été fixés sur un jeu de mise au point (DEV), puis mesurés sur des jeux jamais utilisés (TEST, puis TEST2 : 4 actes téléchargés après la mise au point).

**Écart d’ordre.** L’ordre suivi est celui proposé au §11 de l’audit : d’abord la perte silencieuse, puis le délai moteur. Trois points prévus en Phase C ont été avancés parce qu’ils étaient courts et sans risque de dégradation : la grâce d’arrêt de D-OPS-01, D-OCR-06 et D-PERF-TOK.

## 2. Corrections livrées

| ID | Problème (Phase A) | Correction | Preuve |
|---|---|---|---|
| **D-DET-02** (critique) | Un bloc étranger étiqueté « français » n’était ni traduit ni signalé (statut « déjà français », alerte retirée). | Un bloc étiqueté français est d’abord vérifié : écriture latine, et couverture lexicale française d’au moins 0,85 ou absence de mot nettement étranger. Sinon, le bloc conservé devient `UNCERTAIN / french_label_unverified`, ses alertes sont maintenues et le signalement `FRENCH_LABEL_UNVERIFIED` (gravité erreur) l’envoie en revue humaine. Rien n’est traduit, réécrit ni envoyé au moteur. Version du classificateur : `block-status-7`. | 15 tests : les 15 échouent avant, réussissent après. |
| **D-ENG-01** (critique fonctionnel) | Délai d’appel au moteur figé à 60 s dans le code. | Réglage `TRANSLATOR_PRIVATE_AI_TIMEOUT_SECONDS`, **défaut 60 s inchangé**. Valeurs admises : plus de 0 s, au plus 3 600 s, et toujours inférieures au délai souple de tâche (sinon refus au démarrage). Transmis au moteur et exposé dans Compose et Helm. La valeur cible reste votre décision (§8). | 8 tests (avec D-OPS-01) : les 8 échouent avant. |
| **D-OPS-01** (élevée) | Tâche tuée : document figé en `ANALYZING` ou `TRANSLATING`, sans alerte ; aucune grâce d’arrêt. | Un document en cours dont la dernière écriture dépasse le délai dur + 120 s (aucune tâche vivante n’est possible) devient `FAILED / TASK_LOST`. L’échec est audité et le document se relance par `/analyze`. **Aucune reprise automatique.** Balayage au démarrage du worker, puis au plus toutes les 5 min. Grâce d’arrêt de 1 900 s (supérieure au délai dur de 1 860 s) dans Compose et Helm. | Mêmes 8 tests. Limite Helm : le conteneur OCR du pod reçoit le signal en même temps, et une tâche OCR en cours échoue alors explicitement. |
| **F-L2-03** (élevée) | Terme de glossaire client manqué quand il est collé à une ponctuation (« Bruttogehalt: », « (Nettogehalt) », ponctuation arabe). | Chaque jeton est aussi cherché sans la ponctuation Unicode de ses bords. C’est une union : rien de ce qui était retenu n’est perdu, et la règle de domaine est inchangée. | 16 tests réussissent, 8 échouent sur le code d’origine. Le test `xfail` historique devient un test réel. |
| **D-OCR-06** (élevée) | `OMP_THREAD_LIMIT=1` hérité ralentissait Surya en silence (×3,27). | Le point d’entrée du service Surya retire la variable et écrit un avertissement. Le nombre de fils reste fixé par `OCR_SURYA_THREADS`. | Remesure sur le vrai point d’entrée, même protocole qu’en Phase A, avec la variable héritée : 62,9 / 51,61 / 55,8 s, contre 189,97 / 177,43 / 182,51 s avant correction et 58,49 / 53,87 / 55,81 s sans limite. |
| **D-PERF-TOK** (moyenne) | Tokenizer rechargé depuis le disque pour chaque document. | Cache par processus, indexé par le chemin réel et par le nom, la taille et la date de chaque fichier : toute modification provoque un rechargement. Chargement toujours local, empreinte recalculée, au plus 4 tokenizers en cache. | 4 tests réussissent (4 en erreur avant). Tokenizer réel, 3 chargements successifs : 6,07 / 3,76 / 3,87 s avant ; 5,73 / 0,080 / 0,083 s après. |
| **Langues du RAG** | Le RAG n’acceptait que fr, ar, en, es et de ; un code ISO 639-2 comme `ita` restait non normalisé. | 25 langues : les 5 historiques dans leur ordre, plus les 20 autres langues officielles de l’UE. Alias ISO 639-2/B et /T. En maltais, clés d’alias pour l’article défini attaché (il-/l-, assimilation, contractions), limitées aux entrées maltaises. Aucune autre clé de recherche modifiée. | 44 tests : vrai chemin import → quatre yeux → publication → injection, pour le grec, le bulgare, le polonais et le maltais. Un test existant ajusté : l’exemple de langue hors périmètre passe de l’italien au japonais. |
| **Détection des langues** (trouvé dans la nuit) | Le produit ne reconnaissait que 7 langues : aucune injection RAG possible pour 18 langues de l’UE. | Voir §9. | 48 tests unitaires et 26 tests de bout en bout ; mesures du §9. |

**Fichiers produit et infrastructure modifiés :** 18, pour +2 359 et −62 lignes, dont 1 321 lignes dans deux modules **générés** à partir de sources officielles (`eu_type_lexicons.py`, `eu_lang_markers.py`). Les autres fichiers sont `jobs.py`, `settings.py`, `tasks.py`, `block_status.py`, `language_evidence.py`, `classification.py`, `builder.py`, `service.py`, `linguistic.py` et `normalizer.py`, deux nouveaux modules de la bibliothèque commune, `compose.yaml`, deux fichiers Helm et le point d’entrée Surya. Il n’y a **aucune migration de schéma** et **aucun changement de contrat d’API**. Aucun fichier frontend n’est modifié : l’interface affiche le code de langue tel quel.

## 3. Défauts non traités (état honnête)

| ID | Gravité | Pourquoi non traité | Suite proposée |
|---|---|---|---|
| D-REC-02 | Critique | Il faut d’abord un golden Surya avec tableau (D-REC-01) pour ne pas corriger la reconstruction à l’aveugle. | D-REC-01, puis D-REC-02. |
| D-OPS-02 | Critique | Le découpage des tâches longues (200 pages, 1 800 s) est une refonte d’exécution (Phase C). | Conception à valider. |
| D-REC-01 | Élevée | Golden Surya synthétique non construit dans cette passe. | Prochain lot, avec fils et quantification fixés (D-OCR-07). |
| F-L2-02 | Élevée | Le rognage du prompt touche l’ordre des priorités du contexte ; non fait pour limiter le risque. | Avec un test de priorité glossaire et décisions. |
| D-SUP-01 | Élevée | Les 39 vulnérabilités de Pillow 12.3.0 ne sont corrigées que dans Pillow 13.0.0, version majeure : il faut rejouer le golden et requalifier les pixels du rendu. Côté outillage frontend, npm signale 6 vulnérabilités élevées sur 5 paquets : une seule se corrige sans changement de plage (body-parser) ; les 4 autres (zod, vite, undici, SDK MCP) exigent Angular CLI et Angular build 21.2.29, hors de la plage déclarée. La CI resterait donc rouge après le seul correctif simple. | Branche de maintenance dédiée. |
| D-ENG-04 | Élevée | Le plafond de sortie proportionnel dépend du moteur cible (décision D-ENG-01). | Après votre décision et l’accès au moteur cible. |
| D-REC-03 | Élevée | Qualification visuelle préalable nécessaire. | Après D-REC-01. |
| D-OCR-02 | Élevée | Surya sert une page à la fois ; changement d’architecture OCR (Phase C). | Phase C. |
| D-OCR-07, D-OBS-01, D-CLS-01, D-TEL-01, valeurs financières OCR | Moyenne à faible | Hors de cette passe. | Phase B suite / C. |

**Décisions des lots précédents toujours ouvertes :** licence écrite des poids Surya, orientation des pages (D-OCR-03), accès au moteur cible (service privé et tokenizer Qwen).

## 4. RAG UE : la base de contenu

### 4.1 Contenu versionné (`data/rag-ue/`, 10,5 Mo)

| Jeu | Source | Volume | Usage |
|---|---|---|---|
| EuroVoc 4.24 | Office des publications de l’UE | 894 concepts, 18 microthésaurus (emploi et travail, rémunération, protection sociale, banque, finance, comptabilité, fiscalité, assurance, droit civil, sociétés, migration) ; 20 537 lignes en 23 paires `xx → fr` | Référentiels terminologiques, domaines du produit, sans juridiction |
| Textes du droit du travail | EUR-Lex / CELLAR | 25 actes (24 directives et règlement 883/2004), 571 couples acte-langue, 11 208 articles-langues, avec l’empreinte du HTML d’origine | Base de contenu, **non chargée** (LOT 3) |
| Définitions légales | Les mêmes actes | 1 654 lignes en 22 paires vers le français | Référentiels, domaine `HR`, juridiction `EU` |
| Arabe → français | Wikidata (libellés arabes), aligné sur EuroVoc | 290 lignes, 325 synonymes ; 361 descripteurs couverts sur 839 (43 %) ; 70 descripteurs en liste de revue humaine | Référentiel terminologique `ar → fr` |
| IATE | Base terminologique des institutions | **Non inclus** (export soumis à compte EU Login) | Convertisseur TBX → CSV livré |

### 4.2 Licences et mentions

**EuroVoc.** La licence CC BY 4.0 est déclarée par les métadonnées officielles du jeu de données (`dcterms:license`), dont une copie est jointe. Il faut citer l’attribution et indiquer les modifications. **EUR-Lex.** © Union européenne ; la réutilisation est autorisée avec mention de la source (décision 2011/833/UE). Seuls les textes publiés au Journal officiel font foi. **Wikidata.** CC0 1.0 (domaine public), source tracée ligne par ligne ; le terme français reste le libellé officiel EuroVoc. Le détail, les modifications apportées et les mentions à reproduire figurent dans `data/rag-ue/README.md`.

### 4.3 Contrôles mesurés

- **EuroVoc.** Simulation dans l’importeur de l’API : 20 537 lignes acceptées, 0 erreur, 55 avertissements (53 collisions de synonymes, 3 cibles concurrentes), à arbitrer par les relecteurs.
- **Textes.** 568 couples acte-langue sur 571 ont les mêmes numéros d’articles que le français. Les 3 autres présentent des anomalies **des textes officiels eux-mêmes**. En italien (2000/43/CE) et en espagnol (2000/78/CE), un article « 15 » apparaît en double. En roumain (2002/14/CE), le texte ne compte que 13 articles. Dans ces trois cas, la suite est écartée et signalée, jamais attribuée à un mauvais article.
- **Longueur des articles.** Rapport de longueur au français : médiane 0,918, 90 % entre 0,747 et 1,07, 20 articles sur 10 129 hors de [0,6 ; 1,6], aucun texte vide.
- **Définitions.** Rapport de longueur : médiane 0,907, aucun terme cible tronqué. Importeur : 1 474 lignes acceptées, 180 doublons (même terme défini par plusieurs actes), 0 erreur.
- **Arabe.** Importeur : 0 erreur sur les 290 lignes.
- **Collecte.** 624 couples demandés, 571 obtenus avec langue vérifiée. Les 53 absents sont : la Charte des droits fondamentaux (identifiant refusé par la source, 24 couples) ; l’irlandais pour les 17 directives de 1989 à 2014, absentes de la source dans cette langue ; et 12 langues du règlement 883/2004, absentes de la source.
- **Exactitude.** Évaluation automatique par deux modèles : voir §10.

Ces contrôles sont automatiques. **Aucune ligne n’a été relue par un humain** : c’est l’objet de la validation à quatre yeux.

### 4.4 Intégration au produit

Un outil de plateforme hors API gère la **bibliothèque commune**, dont les référentiels n’ont pas de tenant et sont lisibles par tous les tenants. Il réutilise les briques de l’importeur de l’API : limites, validation ligne à ligne, doublons, formules et instructions. L’import est tout ou rien, et sa trace (empreinte et comptes) est enregistrée dans un événement de validation. Les transitions passent par la fonction de versionnage existante : quatre yeux, empreinte du contenu, index BM25. Les acteurs sont des utilisateurs actifs.

Testé de bout en bout : le même acteur ne peut pas valider sa propre soumission (`RAG_FOUR_EYES_REQUIRED`). Après publication et activation de la paire allemand → français, « contrat de travail » et « salaire minimal » sont injectés chez **deux tenants différents**. Une définition `EU` n’est injectée que si le document déclare la juridiction `EU`. La paire arabe suit le même chemin : un terme arabe publié à quatre yeux est injecté dans la consigne du moteur privé.

### 4.5 Erreurs rencontrées et corrigées pendant la constitution

1. **Premiers outils rejetés.** La première version des outils, produite par un sous-agent, a été rejetée et ses données n’ont pas été utilisées. Les domaines EuroVoc venaient de la mauvaise relation (274 lignes par langue). Les articles étaient repérés par le mot « Article », introuvable dans 22 langues sur 24. Le HTML d’origine n’était pas conservé.
2. **Juridiction EuroVoc.** J’avais d’abord marqué EuroVoc de la juridiction `EU`. Or le produit écarte une entrée à juridiction tant que le document n’en déclare pas une identique : aucune injection n’avait lieu. La correction a porté sur **les données** (juridiction vide pour un thésaurus), pas sur la règle du produit.
3. **Extracteur EUR-Lex.** La première version ne trouvait que 2 articles sur 29 dans un acte au format ancien. Elle n’a pas été livrée. La version livrée est la cinquième, contrôlée langue par langue.
4. **Paire arabe.** La première version comptait 360 lignes. Le premier évaluateur en a jugé 61 incorrectes (exemple : le terme arabe du congé de paternité aligné sur « congé parental »). Seules les paires acceptées par les deux évaluateurs restent importables ; les 70 autres attendent une décision humaine.

### 4.6 Ce que le RAG n’apporte pas

Il n’y a ni recherche sémantique ni vectoriel : l’appariement reste lexical (forme exacte, synonymes, alias). Les textes intégraux ne sont pas interrogeables par le produit (LOT 3). L’effet sur la qualité de traduction n’est pas mesuré : il faut le moteur cible et une relecture humaine. L’API limite toujours à 20 le nombre de langues déclarées par référentiel. Je ne l’ai pas modifiée, pour préserver le contrat. L’outil crée donc un référentiel par paire de langues.

## 5. Non-régression

### 5.1 Règles de mesure v3, v4 et v5

La fermeture de mesure gelée change trois fois, chaque fois avec une justification et des mesures inscrites dans le test d’empreinte. Les références antérieures restent inscrites (v2 `d5c31e6d701c1c9d`, Surya ; v1 `b0b0261eaabecda8`).

- **v3 (`6c50972530ecc214`, 29 + 5 fichiers).** `block_status.py` et `language_evidence.py` (D-DET-02) : les comptes de statuts de blocs et de signalements « non traduit » mesurés sous v2 **ne sont plus comparables**. `builder.py` (F-L2-03) : les mesures de conformité au glossaire sous v2 **ne sont plus comparables**. `service.py` (D-PERF-TOK) : cache seul, effet neutre sur les sorties.
- **v4 (`13fb843ac56930b4`, 30 + 5).** `classification.py` et `language_evidence.py` changent, `eu_type_lexicons.py` est ajouté (détection et classement des langues ajoutées). Mesuré : corpus bancaire identique ; 3 paragraphes historiques sur 1 486 changeaient (déjà faux, ou « inconnu » devenu faux).
- **v5 (`d141744e65948764`, 31 + 5).** `classification.py` change, `eu_lang_markers.py` est ajouté (irlandais et maltais courts, gardes de non-régression). Mesuré : corpus bancaire identique, et **les écarts de la v4 disparaissent** : 2 229 paragraphes historiques sur 2 229 ont la même langue principale et la même liste de langues qu’avec le code d’origine.

### 5.2 Régressions introduites puis corrigées

1. **D-DET-02 (3 novembre).** La première suite complète a donné **2 échecs, causés par ma correction**. Deux anciens tests (F50 et F53) exigeaient le préfixe exact `block-status-6`, alors que D-DET-02 fait passer la version à `block-status-7`, selon la convention du module. Ils exigent désormais une version **au moins égale à 6**.
2. **Détection, premier essai (nuit).** Les indices irlandais et maltais s’accumulaient sur de longs documents français, anglais ou italiens, et des sous-chaînes courtes (« iva ») faisaient basculer un document suédois. Le corpus bancaire l’a révélé avant tout commit. Correction : densité minimale des indices, comparaison en mot entier.
3. **Marqueurs irlandais et maltais, première version.** Un texte français contenant « au fil » ou « méta » recevait le maltais en langue secondaire. Correction : tout marqueur attesté dans une autre langue (dictionnaire de fréquences wordfreq) est exclu. Le texte adverse redonne exactement le résultat d’origine.
4. **Langues historiques (v4).** Une ligne anglaise de 4 mots et un mot néerlandais isolé recevaient une langue ajoutée. Correction : la voie statistique ne peut plus attribuer une langue ajoutée à un seul mot, ni à un texte dont tous les mots sont courants dans une langue historique. Coût mesuré : 5 paragraphes justes perdus sur 6 456 en langues ajoutées (portugais ambigu avec l’espagnol, mots isolés).

### 5.3 Vérification finale (même jeu de commandes qu’en Phase A)

Vérification rejouée sur le commit final des sources, arbre propre ; empreintes du code et des tests identiques au début et à la fin de l’exécution.

| Contrôle | Phase A (base auditée) | Phase B, 3 novembre | Phase B finale (4 novembre) |
|---|---|---|---|
| `ruff check backend tools services` (commande de la CI) | OK | OK | OK |
| Suite backend (unit, integration, e2e, regression, security) | 1 031 réussis, 2 ignorés, 1 xfail | 1 128 réussis, 2 ignorés, 0 échec | **1 207 réussis, 2 ignorés, 0 échec** (615 s) |
| Golden (8 cas, chemin Tesseract explicite ; ne qualifie pas Surya) | 8 réussis | 8 réussis | **8 réussis** (1 221 s) |
| PostgreSQL (migration RAG et BM25, base jetable) | 3 réussis | 3 réussis | **3 réussis** |
| Autotest du service Surya (hors réseau) | OK | OK | OK |
| Compose (`config`) et Helm (`lint`, `template`) | OK | OK | OK ; grâce d’arrêt présente (Helm : 11 objets) |
| `pip-audit` à date | échec (Pillow) | échec : 39 vulnérabilités, Pillow seul | échec inchangé : 39 vulnérabilités, Pillow seul |
| Frontend | 30 réussis | non relancé : aucun fichier modifié | non relancé : aucun fichier modifié |

La comparaison des collectes, identifiant par identifiant, donne **175 tests nouveaux et 0 disparu** depuis la Phase A. Un seul statut change : l’ancien `xfail` de F-L2-03 réussit désormais. Depuis la vérification du 3 novembre, les 79 tests ajoutés sont : 48 pour la détection, 26 pour le parcours complet des langues, 5 pour la paire arabe.

**Contrôles qui n’avaient pas réellement tourné, ou mesures invalides, à cause de mon outillage.** Je ne les ai jamais comptés comme réussis. (1) Au premier passage du 3 novembre, le golden avait collecté 0 cas (jeu privé absent du worktree neuf) et le conteneur PostgreSQL n’avait pas démarré (réseau pont Docker absent) : les deux ont été rejoués, sur l’arbre exporté du commit et en réseau hôte sur écoute locale. (2) Une vérification nocturne a été **interrompue volontairement**, car j’avais modifié des données pendant son exécution : elle a été relancée sur le commit figé. (3) Une première mesure des gardes de détection était invalide : une variable d’environnement de ma session pointait vers un autre jeu de données. Elle a été refaite.

## 6. Publication

Chaque dépôt reçoit la branche `feature/lot23-phase-b-20261103` et une PR **brouillon** vers la branche des rapports de Phase A. Dans le dépôt de travail, la branche porte l’historique des commits. Dans le second dépôt (privé, destiné à être ouvert), elle porte un **instantané assaini** : le même contenu, avec une seule différence, l’empreinte du commit de Phase 0 citée dans un commentaire de test. Ce second dépôt ne contient ni historique de travail, ni document, ni poids, ni secret, ni chemin local.

Les données EuroVoc, EUR-Lex et Wikidata sont des données publiques réutilisables, avec mentions. Il n’y a ni fusion ni déploiement. **Le second dépôt reste privé jusqu’à votre ordre.**

## 7. Limites et risques

- **Qualification humaine absente.** Aucune donnée RAG n’a été relue. La validation à quatre yeux est obligatoire avant toute publication, quel que soit le résultat des contrôles automatiques.
- **Évaluateurs automatiques.** Ce sont deux modèles du même fournisseur, dont les erreurs peuvent être corrélées. Ils se trompent aussi : deux de leurs rejets EUR-Lex portent sur des termes extraits mot pour mot du texte officiel.
- **Gain non mesuré.** Le bénéfice du RAG sur la traduction n’est pas mesuré ; le moteur cible n’est pas disponible.
- **Fragments courts.** Les titres et cellules de tableau de 20 à 60 caractères ne sont reconnus qu’à 86,4 % dans les langues ajoutées : 9,8 % restent « inconnu » et 3,8 % reçoivent une langue fausse. La langue du document, calculée sur la concaténation de tous ses blocs, relève du cas des paragraphes longs (100 %).
- **Langues fausses.** Elles viennent surtout des langues historiques, prioritaires par construction : l’irlandais pris pour de l’anglais (10 cas sur 240) ou de l’espagnol (4), le finnois pour de l’anglais (4), le slovène pour de l’allemand (4). Entre langues ajoutées, la confusion principale est slovène / croate (5).
- **OCR.** Contrôle sur une page propre par langue, pas une qualification : arabe à 0,945 de F1 (1 vraie erreur sur 43 mots arabes), traits d’union perdus en maltais. Les tableaux scannés (D-REC-02), l’orientation et les scans très dégradés ne sont pas couverts.
- **Définitions UE et droit national.** Une définition légale de l’UE n’est pas toujours le terme du droit national applicable ; le relecteur doit le vérifier.
- **D-OPS-01.** La détection est a posteriori (délai dur + 120 s). Elle signale la perte mais ne la répare pas ; la reprise automatique reste à concevoir (Phase C).
- **D-DET-02.** La vérification lexicale peut envoyer en revue un bloc réellement français mais atypique (sigles, tableaux de chiffres). C’est voulu : un faux positif coûte une revue, une perte silencieuse coûte la fidélité.
- **CI.** La CI reste rouge sur les audits de dépendances (D-SUP-01) : Pillow 13 et les nouvelles versions de l’outillage npm sont des montées majeures, non faites de nuit pour ne pas dégrader l’existant.

## 8. Décisions demandées

1. **Relecture et publication RAG.** Désigner les deux personnes (soumission et validation) pour les référentiels de la bibliothèque commune, et choisir les paires et les domaines à publier en premier. Trancher les 70 descripteurs arabes de la liste de revue.
2. **IATE.** Fournir un export TBX ciblé (domaines travail, banque et finance), obtenu avec votre compte EU Login, si vous souhaitez l’intégrer.
3. **D-ENG-01 et D-ENG-04.** Valeur cible du délai moteur et plafond de sortie, selon le moteur et le débit de production.
4. **Suite de la Phase B.** Ordre proposé : D-SUP-01 (Pillow 13, avec requalification du golden), D-REC-01 (golden Surya avec tableau), D-REC-02, F-L2-02.
5. **LOT 3** (recherche juridique sur les textes EUR-Lex chargés) : non engagé sans votre validation explicite.
6. **Ouverture publique** du second dépôt : uniquement sur votre ordre.

**Production : NO-GO.** Rien dans cette phase ne lève ce statut. Il manque la licence écrite des poids Surya, la qualification humaine et documentaire, le moteur cible et les défauts critiques D-REC-02 et D-OPS-02.

## 9. Toutes les langues : détection, classement, RAG et OCR

### 9.1 Détection des langues

**Avant.** Le détecteur reconnaissait 7 langues. Il s’appuie sur un détecteur statistique (langdetect, graine fixe) qui connaît 16 des 18 autres langues de l’UE, mais le produit n’en retenait aucune. L’irlandais et le maltais ne sont connus d’aucun détecteur installé.

**Après.** Les 7 langues historiques passent toujours en premier, avec exactement les mêmes règles. Une langue ajoutée n’est retenue que sur preuve forte :

- **voie statistique** : probabilité d’au moins 0,90, confirmée sur le texte en minuscules, au moins 20 lettres, au moins deux mots, et pas un texte fait uniquement de mots courants d’une langue historique ;
- **écriture** : le grec par son alphabet ;
- **irlandais et maltais** : marqueurs distinctifs générés depuis les textes EUR-Lex de mise au point (mots fréquents dans la langue, absents des autres langues et du dictionnaire de fréquences des 23 autres langues), avec une densité minimale.

À défaut, le bloc reste « inconnu », comme avant.

**Mesure sur des textes jamais utilisés pour la mise au point.** Paragraphes d’articles officiels EUR-Lex, tirés par acte et par langue, en trois tranches de longueur égales : courts (20 à 60 caractères), moyens (60 à 200), longs (200 à 600). TEST : actes du corpus réservés dès le départ (partage par empreinte du numéro CELEX) ; TEST2 : 4 actes récents téléchargés après la mise au point (directive crédit aux consommateurs 2023/2225, services financiers à distance 2023/2673, équilibre femmes-hommes 2022/2381, devoir de vigilance 2024/1760).

| Mesure (18 langues ajoutées, TEST + TEST2) | Résultat | Borne basse Wilson 95 % |
|---|---:|---:|
| Langue juste, toutes longueurs | 4 108 / 4 320 = **95,09 %** | 94,41 % |
| Langue fausse | 62 / 4 320 = 1,44 % | — |
| Paragraphes longs (200 à 600 caractères) | 1 440 / 1 440 = **100 %** | 99,73 % |
| Paragraphes moyens (60 à 200) | 1 424 / 1 440 = 98,89 % | 98,20 % |
| Fragments courts (20 à 60) | 1 244 / 1 440 = 86,39 % | 84,52 % |
| Code d’origine, mêmes textes | 0 / 4 320 | — |

Par langue (240 paragraphes chacune) : estonien 98,3 %, hongrois 98,8 %, roumain 98,3 %, maltais 97,5 %, grec 97,1 %, polonais 97,1 %, tchèque 96,2 %, finnois 95,8 %, letton 94,6 %, lituanien 94,6 %, suédois 94,6 %, croate 94,2 %, portugais 93,8 %, slovaque 93,3 %, bulgare 92,5 %, danois 92,5 %, slovène 91,7 %, irlandais 90,8 %.

**Langues historiques : aucun changement.** Sur 2 229 paragraphes officiels en anglais, français, allemand, italien, espagnol et néerlandais (DEV, TEST, TEST2), la langue principale et la liste de langues sont **identiques** au code d’origine (borne basse 99,83 %). Sur les 646 documents à texte du corpus bancaire Maroc/MRE (les 119 scans sans couche texte n’ont pas de texte à détecter), la langue **et** le classement (type, domaine, confiance, scores) sont identiques (borne basse 99,41 %).

### 9.2 Classement par type de document

Le classement (attestation d’emploi, bulletin de paie, relevé bancaire, contrat, facture, document administratif) reposait sur des lexiques en langues historiques. Un document grec n’avait donc aucun indice lexical de type, et le RAG lui appliquait un domaine indéterminé. Un module généré ajoute 342 expressions officielles EuroVoc (18 langues, 6 types). Elles ne sont consultées que pour une langue détectée dans le document, en mot entier : sans effet sur les documents en langues historiques (corpus bancaire identique).

### 9.3 Parcours complet par langue

Un test de bout en bout par langue source (24 : les 23 langues de l’UE autres que le français, plus l’arabe) passe par le vrai chemin du produit : envoi d’un DOCX par l’API, analyse, langue détectée, domaine `HR`, recherche RAG, puis injection du terme EuroVoc publié à quatre yeux dans la consigne du moteur privé simulé. Le document contient un intitulé d’attestation d’emploi et un paragraphe officiel EUR-Lex dans la langue ; pour l’arabe, qui n’a pas de texte EUR-Lex, une phrase synthétique. Un document témoin en français reste français et ne reçoit aucune entrée étrangère. **26 tests sur 26 réussissent** (279 s).

### 9.4 OCR Surya dans les 24 langues

**Mesure.** Une page par langue passe par le point d’entrée Surya de la branche, en configuration produit (Q8_0, 4 fils, `--cache-ram 0`). 18 pages viennent du banc S1 du LOT 2.2 (paragraphe synthétique et tableau, numérisation simulée). Les 6 langues absentes de S1 (estonien, finnois, irlandais, lituanien, letton, maltais) ont des pages produites par la même chaîne (DOCX avec tableau, PDF, numérisation simulée à 250 dpi avec bruit, rotation de 0,5° et JPEG 80, image à 144 dpi), à partir du même article de la directive 2023/2225 (TEST2) dans chaque langue, plus un témoin français. Métriques identiques à S1 : F1 sur les mots (forme Unicode et casse normalisées) et CER dépendant de l’ordre.

| Pages | Résultat |
|---|---|
| Toutes (26) | 26 sur 26 traitées sans erreur, 54 à 69 s par page |
| 24 langues de l’UE | **F1 ≥ 0,95 sur 24 pages sur 24**, moyenne 0,994 |
| 18 pages du banc S1 | F1 identique, page par page, à la référence bf16 du LOT 2.2 : la quantification Q8_0 ne coûte rien ici |
| 6 langues nouvelles | F1 1,000 en estonien, finnois, irlandais, lituanien et letton ; maltais 0,958 : mots justes, mais trait d’union des articles attachés perdu (« fl-artikolu » lu « flartikolu », 3 cas) ; témoin français 1,000 |
| Arabe | F1 **0,945** contre le texte d’origine : 1 vraie erreur (deux lettres inversées), 1 voyelle brève perdue, 1 code alphanumérique mal découpé |

**Erreur de mesure trouvée et corrigée.** Contre la référence S1, l’arabe obtenait 0,83. Or cette référence, extraite de la couche texte du PDF, est fausse pour l’arabe : ligatures lam-alef décomposées, voyelles déplacées, espaces manquants. Au moins 10 des 13 mots « manqués » étaient en réalité bien lus. J’ai reconstruit la référence à partir du texte d’origine du générateur ; la reconstruction redonne exactement les scores S1 sur les pages allemande, grecque et bulgare. Le CER de l’arabe (0,13) reste élevé, car il dépend de l’ordre des segments écrits de droite à gauche et de gauche à droite.

**Portée.** Une page propre par langue, sans dégradation forte : c’est un contrôle de fonctionnement, pas une qualification OCR. Il ne remplace ni le golden Surya avec tableau (D-REC-01), ni la qualification humaine, ni la licence des poids, et il ne couvre pas la limitation d’orientation déjà connue.

## 10. Indice de confiance (pré-déclaré, jugé par moi)

**Méthode, fixée avant les mesures.** Chaque composante mesurable sur échantillon reçoit sa borne basse de Wilson à 95 %. Le seuil est de 92 % pour **chaque** composante, et non pour une moyenne. Les tests déterministes (suite, parcours complet) doivent réussir sans exception. Les sous-groupes sous le seuil sont nommés.

**Évaluation automatique de l’exactitude du contenu RAG.** Un échantillon stratifié, tiré au sort avec une graine fixe, a été soumis à deux modèles de langue récents utilisés comme évaluateurs (verdict `correct`, `acceptable` ou `incorrect`, avec motif, sous un schéma de réponse strict). Ils ne reçoivent que des données publiques. **Ce n’est pas une revue humaine.**

| Données | Paires | 1er évaluateur : non incorrect | 2e évaluateur : non incorrect | Accord |
|---|---:|---:|---:|---:|
| Définitions EUR-Lex (10 par langue) | 220 | 220 (100 %) | 218 (99,1 %) | 99,1 % |
| EuroVoc (15 par langue) | 345 | 335 (97,1 %) | 336 (97,4 %) | 97,4 % |
| Arabe Wikidata | 360, puis 299 | 299 (83,1 %) | 290 sur 299 (97,0 %) | — |

**Tableau de l’indice.**

| Composante | Mesure | Résultat | Borne basse 95 % | Seuil 92 % |
|---|---|---:|---:|:---:|
| Définitions EUR-Lex exactes | Non incorrectes pour les deux évaluateurs | 218 / 220 = 99,09 % | 96,75 % | atteint |
| EuroVoc exact | Non incorrect pour les deux évaluateurs | 331 / 345 = 95,94 % | **93,30 %** | atteint |
| Arabe importable exact | 2e évaluateur, sur les paires retenues par le 1er | 290 / 299 = 96,99 % | 94,38 % | atteint |
| Détection des 18 langues ajoutées | Textes jamais vus, toutes longueurs | 4 108 / 4 320 = 95,09 % | 94,41 % | atteint |
| Langues historiques inchangées | Paragraphes officiels | 2 229 / 2 229 identiques | 99,83 % | atteint |
| Corpus bancaire inchangé | Langue et classement | 646 / 646 identiques | 99,41 % | atteint |
| OCR Surya, une page par langue | Contrôle de fonctionnement (pas un échantillon) | 24 / 24 langues de l’UE à F1 ≥ 0,95 ; arabe 0,945 | — | réussi, hors estimation |
| Parcours complet par langue | Test déterministe | 24 / 24 langues + témoin | — | réussi |
| Suite backend complète | Test déterministe | 1 207 réussis, 0 échec | — | réussie |

**Sous le seuil, et donc hors de l’affirmation :** fragments de 20 à 60 caractères (86,39 %, borne 84,52 %), irlandais (90,8 %) et slovène (91,7 %) en estimation ponctuelle ; bulgare et danois sont à 92,5 %. Le parcours complet par langue est un test déterministe : avec seulement 24 cas, il ne permettrait pas, à lui seul, une borne statistique supérieure à 86 %, et je ne le présente pas comme une estimation.

**Mon jugement.** Je juge la confiance **au moins égale à 92 %** pour l’affirmation suivante : « les 24 langues de l’UE et l’arabe sont reconnues et prises en charge par le RAG, le contenu livré est exact, et rien n’a régressé pour l’existant ». La plus faible borne basse est de 93,30 %. Cette confiance **ne porte pas** sur la qualité des traductions, ni sur la conformité au droit national, ni sur l’aptitude à la production. Elle ne remplace pas la relecture humaine, qui reste obligatoire quel que soit le score.
