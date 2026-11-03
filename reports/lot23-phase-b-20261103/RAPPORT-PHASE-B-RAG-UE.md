# LOT 2.3, Phase B : corrections et RAG UE (terminologie et droit du travail de l’Union européenne)

**Date :** 3 novembre 2026. **Auteur et committer de tous les commits :** Hamza NORDINE. **Branche :** `feature/lot23-phase-b-20261103`, construite sur `feature/lot23-qualification-20261102` (rapports de Phase A). **Dépôts :** les deux dépôts sont **privés** jusqu’à nouvel ordre. **Production : NO-GO**, inchangé.

## 0. Synthèse

Le 3 novembre, la consigne a été la suivante : « Corrige ce qu’il y a et constitue ton RAG depuis ce que tu trouves sur internet avec des dictionnaires de traduction de toutes les langues de l’Union européenne plus les lois du travail de l’UE ; push tout sur Git avec la base de contenu du RAG ; Git en privé jusqu’à l’ordre d’ouvrir en public ; évite toute dégradation de l’existant. » Je l’ai traitée comme la validation de la Phase A et l’autorisation de la Phase B, y compris pour les fichiers gelés, à condition de prouver la non-régression.

**Corrections.** Six défauts de l’audit de Phase A sont corrigés, ainsi que la limitation du RAG à 5 langues. Chaque correction a des tests qui échouent sur le code d’origine et réussissent après correction :

- D-DET-02 : perte silencieuse de blocs étiquetés « français » ;
- D-ENG-01 : délai moteur figé dans le code ;
- D-OPS-01 : tâches perdues sans alerte, et grâce d’arrêt ;
- F-L2-03 : terme de glossaire collé à une ponctuation ;
- D-OCR-06 : `OMP_THREAD_LIMIT` hérité par Surya ;
- D-PERF-TOK : tokenizer rechargé à chaque document ;
- la limitation du RAG à 5 langues.

Les valeurs par défaut sont conservées chaque fois qu’un changement pouvait dégrader l’existant. Par exemple, le délai moteur reste à 60 s par défaut. **Douze défauts de l’audit ne sont pas traités**, plus les valeurs financières OCR. Deux d’entre eux sont critiques (D-REC-02, D-OPS-02). Tous sont détaillés au §3.

**RAG UE.** Le RAG accepte désormais les **24 langues officielles de l’UE**, en plus de l’arabe. La base de contenu est versionnée dans le dépôt :

- **EuroVoc 4.24** : 20 537 lignes en 23 paires vers le français, sous licence CC BY 4.0 ;
- **25 actes du droit du travail de l’UE**, issus d’EUR-Lex : 571 couples acte-langue et 11 208 articles-langues ;
- **1 654 définitions légales** alignées point par point vers le français.

Un outil de plateforme charge ces données dans la **bibliothèque commune**, toujours en brouillon. La validation y reste à quatre yeux et l’activation explicite. **IATE n’est pas inclus** : son export exige un compte EU Login. Un convertisseur est livré pour l’export que vous fournirez.

**Ce que le RAG apporte, sans l’exagérer.** Il améliore la cohérence terminologique (terme français institutionnel), uniquement en mode `ACTIVE` avec le moteur privé. Le mode par défaut reste `DISABLED`. Ce gain n’est **pas mesuré** sur des traductions réelles, et aucune relecture humaine n’a été faite. Les textes intégraux ne sont pas encore interrogeables par le produit : la recherche juridique relève du LOT 3.

**Non-régression.**

- La suite complète a d’abord révélé **2 échecs causés par ma correction D-DET-02** (version de classificateur figée par deux anciens tests). Ils ont été corrigés et sont documentés au §5.
- Vérification finale sur le commit des sources : suite backend **1 128 réussis, 2 ignorés, 0 échec** (96 tests nouveaux, aucun disparu) ; golden **8/8** ; PostgreSQL **3/3** ; Compose et Helm OK. L’audit des dépendances échoue toujours sur Pillow (D-SUP-01, inchangé).
- La règle de mesure passe en **v3** (empreinte `6c50972530ecc214`). Les références v2 et v1 sont conservées, et les mesures qui ne sont plus comparables sont nommées.

## 1. Périmètre et règles appliquées

**Base.** La branche part du commit des rapports de Phase A, lui-même placé sur la branche Surya auditée. Elle compte 12 commits de code, de tests, de données et de documentation, auxquels s’ajoute le commit de ce rapport (avec une précision du README des données). Il n’y a ni fusion dans `main`, ni déploiement, ni démarrage du LOT 3.

**Règles.**

- Chaque correction a un test qui échoue sur le code d’origine, ce qui est vérifié en rejouant le test sur l’arbre d’origine.
- Aucun comportement par défaut n’est modifié quand le changement peut dégrader l’existant.
- Le RAG reste `DISABLED` par défaut, sans base vectorielle, sans Qdrant ni BGE-M3.
- Rien n’est publié automatiquement dans le RAG.
- Les sources sont officielles et réutilisables, avec licence vérifiée.
- Aucune aspiration ni contournement n’a été fait (IATE).
- Aucune donnée client n’a été manipulée.

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

**Fichiers produit et infrastructure modifiés :** 15, pour +815 et −58 lignes. Il s’agit de `jobs.py`, `settings.py`, `tasks.py`, `block_status.py`, `language_evidence.py`, `builder.py`, `service.py`, `linguistic.py` et `normalizer.py`, de deux nouveaux modules de la bibliothèque commune, de `compose.yaml`, de deux fichiers Helm et du point d’entrée Surya. Il n’y a **aucune migration de schéma** et **aucun changement de contrat d’API**.

## 3. Défauts non traités (état honnête)

| ID | Gravité | Pourquoi non traité | Suite proposée |
|---|---|---|---|
| D-REC-02 | Critique | Il faut d’abord un golden Surya avec tableau (D-REC-01) pour ne pas corriger la reconstruction à l’aveugle. | D-REC-01, puis D-REC-02. |
| D-OPS-02 | Critique | Le découpage des tâches longues (200 pages, 1 800 s) est une refonte d’exécution (Phase C). | Conception à valider. |
| D-REC-01 | Élevée | Golden Surya synthétique non construit dans cette passe. | Prochain lot, avec fils et quantification fixés (D-OCR-07). |
| F-L2-02 | Élevée | Le rognage du prompt touche l’ordre des priorités du contexte ; non fait pour limiter le risque. | Avec un test de priorité glossaire et décisions. |
| D-SUP-01 | Élevée | Pillow 13 est une version majeure : il faut rejouer le golden et qualifier les pixels. | Branche de maintenance dédiée. |
| D-ENG-04 | Élevée | Le plafond de sortie proportionnel dépend du moteur cible (décision D-ENG-01). | Après votre décision et l’accès au moteur cible. |
| D-REC-03 | Élevée | Qualification visuelle préalable nécessaire. | Après D-REC-01. |
| D-OCR-02 | Élevée | Surya sert une page à la fois ; changement d’architecture OCR (Phase C). | Phase C. |
| D-OCR-07, D-OBS-01, D-CLS-01, D-TEL-01, valeurs financières OCR | Moyenne à faible | Hors de cette passe. | Phase B suite / C. |

**Décisions des lots précédents toujours ouvertes :** licence écrite des poids Surya, orientation des pages (D-OCR-03), accès au moteur cible (service privé et tokenizer Qwen).

## 4. RAG UE : la base de contenu

### 4.1 Contenu versionné (`data/rag-ue/`, 10,2 Mo)

| Jeu | Source | Volume | Usage |
|---|---|---|---|
| EuroVoc 4.24 | Office des publications de l’UE | 894 concepts, 18 microthésaurus (emploi et travail, rémunération, protection sociale, banque, finance, comptabilité, fiscalité, assurance, droit civil, sociétés, migration) ; 20 537 lignes en 23 paires `xx → fr` | Référentiels terminologiques, domaines du produit, sans juridiction |
| Textes du droit du travail | EUR-Lex / CELLAR | 25 actes (24 directives et règlement 883/2004), 571 couples acte-langue, 11 208 articles-langues, avec l’empreinte du HTML d’origine | Base de contenu, **non chargée** (LOT 3) |
| Définitions légales | Les mêmes actes | 1 654 lignes en 22 paires vers le français | Référentiels, domaine `HR`, juridiction `EU` |
| IATE | Base terminologique des institutions | **Non inclus** (export soumis à compte EU Login) | Convertisseur TBX → CSV livré |

### 4.2 Licences et mentions

**EuroVoc.** La licence CC BY 4.0 est déclarée par les métadonnées officielles du jeu de données (`dcterms:license`), dont une copie est jointe. Il faut citer l’attribution et indiquer les modifications. **EUR-Lex.** © Union européenne ; la réutilisation est autorisée avec mention de la source (décision 2011/833/UE). Seuls les textes publiés au Journal officiel font foi. Le détail, les modifications apportées et les mentions à reproduire figurent dans `data/rag-ue/README.md`.

### 4.3 Contrôles mesurés

- **EuroVoc.** Simulation dans l’importeur de l’API : 20 537 lignes acceptées, 0 erreur, 55 avertissements (53 collisions de synonymes, 3 cibles concurrentes), à arbitrer par les relecteurs.
- **Textes.** 568 couples acte-langue sur 571 ont les mêmes numéros d’articles que le français. Les 3 autres présentent des anomalies **des textes officiels eux-mêmes**. En italien (2000/43/CE) et en espagnol (2000/78/CE), un article « 15 » apparaît en double. En roumain (2002/14/CE), le texte ne compte que 13 articles. Dans ces trois cas, la suite est écartée et signalée, jamais attribuée à un mauvais article.
- **Longueur des articles.** Rapport de longueur au français : médiane 0,918, 90 % entre 0,747 et 1,07, 20 articles sur 10 129 hors de [0,6 ; 1,6], aucun texte vide.
- **Définitions.** Rapport de longueur : médiane 0,907, aucun terme cible tronqué. Importeur : 1 474 lignes acceptées, 180 doublons (même terme défini par plusieurs actes), 0 erreur.
- **Collecte.** 624 couples demandés, 571 obtenus avec langue vérifiée. Les 53 absents sont : la Charte des droits fondamentaux (identifiant refusé par la source, 24 couples) ; l’irlandais pour les 17 actes antérieurs à 2014, qui n’existent pas dans cette langue ; et 12 langues du règlement 883/2004, absentes de la source.

Ces contrôles sont automatiques. **Aucune ligne n’a été relue par un humain** : c’est l’objet de la validation à quatre yeux.

### 4.4 Intégration au produit

Un outil de plateforme hors API gère la **bibliothèque commune**, dont les référentiels n’ont pas de tenant et sont lisibles par tous les tenants. Il réutilise les briques de l’importeur de l’API : limites, validation ligne à ligne, doublons, formules et instructions. L’import est tout ou rien, et sa trace (empreinte et comptes) est enregistrée dans un événement de validation. Les transitions passent par la fonction de versionnage existante : quatre yeux, empreinte du contenu, index BM25. Les acteurs sont des utilisateurs actifs.

Testé de bout en bout : le même acteur ne peut pas valider sa propre soumission (`RAG_FOUR_EYES_REQUIRED`). Après publication et activation de la paire allemand → français, « contrat de travail » et « salaire minimal » sont injectés chez **deux tenants différents**. Une définition `EU` n’est injectée que si le document déclare la juridiction `EU`.

### 4.5 Erreurs rencontrées et corrigées pendant la constitution

1. **Premiers outils rejetés.** La première version des outils, produite par un sous-agent, a été rejetée et ses données n’ont pas été utilisées. Les domaines EuroVoc venaient de la mauvaise relation (274 lignes par langue). Les articles étaient repérés par le mot « Article », introuvable dans 22 langues sur 24. Le HTML d’origine n’était pas conservé.
2. **Juridiction EuroVoc.** J’avais d’abord marqué EuroVoc de la juridiction `EU`. Or le produit écarte une entrée à juridiction tant que le document n’en déclare pas une identique : aucune injection n’avait lieu. La correction a porté sur **les données** (juridiction vide pour un thésaurus), pas sur la règle du produit.
3. **Extracteur EUR-Lex.** La première version ne trouvait que 2 articles sur 29 dans un acte au format ancien. Elle n’a pas été livrée. La version livrée est la cinquième, contrôlée langue par langue.

### 4.6 Ce que le RAG n’apporte pas

Il n’y a ni recherche sémantique ni vectoriel : l’appariement reste lexical (forme exacte, synonymes, alias). Les textes intégraux ne sont pas interrogeables par le produit (LOT 3). L’effet sur la qualité de traduction n’est pas mesuré : il faut le moteur cible et une relecture humaine. L’API limite toujours à 20 le nombre de langues déclarées par référentiel. Je ne l’ai pas modifiée, pour préserver le contrat. L’outil crée donc un référentiel par paire de langues.

## 5. Non-régression

### 5.1 Règle de mesure v3

Quatre fichiers de la fermeture de mesure gelée changent ; aucun n’est ajouté ni retiré (29 fichiers produit et 5 fichiers outils) :

- `block_status.py` et `language_evidence.py` (D-DET-02) : les comptes de statuts de blocs et de signalements « non traduit » mesurés sous v2 **ne sont plus comparables** ;
- `builder.py` (F-L2-03) : les mesures de conformité au glossaire sous v2 **ne sont plus comparables** ;
- `service.py` (D-PERF-TOK) : cache seul, effet neutre sur les sorties.

Nouvelle empreinte : `6c50972530ecc214`. Les empreintes v2 (`d5c31e6d701c1c9d`, Surya) et v1 (`b0b0261eaabecda8`) restent inscrites dans le test, avec leurs justifications.

### 5.2 Régression introduite puis corrigée

La première suite complète (1 122 tests réussis, 3 ignorés) a donné **2 échecs, causés par ma correction D-DET-02**. Deux anciens tests (F50 et F53) exigeaient le préfixe exact `block-status-6`, alors que D-DET-02 fait passer la version à `block-status-7`, selon la convention du module. Ces tests garantissaient que leur propre correction était incluse dans la version. Ils exigent désormais une version **au moins égale à 6**. Les 53 tests concernés réussissent.

### 5.3 Vérification finale (même jeu de commandes qu’en Phase A)

| Contrôle | Phase A (base auditée) | Phase B (HEAD des sources) |
|---|---|---|
| `ruff check backend tools services` (commande de la CI) | OK | OK |
| Suite backend (unit, integration, e2e, regression, security) | 1 031 réussis, 2 ignorés, 1 xfail | **1 128 réussis, 2 ignorés, 0 échec** (290 s) |
| Golden (8 cas, chemin Tesseract explicite ; ne qualifie pas Surya) | 8 réussis | **8 réussis** (1 077 s) |
| PostgreSQL (migration RAG et BM25, base jetable) | 3 réussis | **3 réussis** |
| Autotest du service Surya (hors réseau) | OK | OK |
| Compose (`config`) et Helm (`lint`, `template`) | OK | OK ; grâce d’arrêt présente dans le rendu Compose et dans le rendu Helm (11 objets) |
| `pip-audit` à date | échec (Pillow, D-SUP-01) | échec inchangé : 39 vulnérabilités, 1 paquet (Pillow) |
| Frontend | 30 réussis | non relancé : **aucun fichier frontend modifié** |
| `ruff format --check` (hors CI) | 24 fichiers non formatés | 24 fichiers, **liste identique**, aucun touché en Phase B |

La comparaison des collectes, identifiant par identifiant, donne **96 tests nouveaux et 0 disparu**. Un seul statut change : l’ancien `xfail` de F-L2-03 réussit désormais. Les 96 nouveaux tests se répartissent ainsi : 44 pour les langues de l’UE, 15 pour D-DET-02, 14 pour F-L2-03, 8 pour D-ENG-01 et D-OPS-01, 4 pour D-PERF-TOK, 4 pour EuroVoc et la bibliothèque commune, 4 pour IATE et 3 pour EUR-Lex.

**Deux contrôles n’avaient pas réellement tourné au premier passage**, par erreur de mon outillage. Je ne les ai pas comptés comme réussis. Le golden avait collecté 0 cas : son jeu privé (`dataset/`, ignoré par Git) était absent du worktree neuf. Il a été rejoué sur l’arbre exporté du même commit, avec ce jeu privé, sans rien copier dans le dépôt. Le conteneur PostgreSQL n’avait pas démarré, faute de réseau pont Docker. Il a été relancé en réseau hôte, sur une écoute locale uniquement. Les résultats ci-dessus sont ceux de cette reprise.

## 6. Publication

Chaque dépôt reçoit la branche `feature/lot23-phase-b-20261103` et une PR **brouillon** vers la branche des rapports de Phase A. Dans le dépôt de travail, la branche porte l’historique des commits. Dans le second dépôt (privé, destiné à être ouvert), elle porte un **instantané assaini** : le même contenu, avec une seule différence, l’empreinte du commit de Phase 0 citée dans un commentaire de test. Ce second dépôt ne contient ni historique de travail, ni document, ni poids, ni secret, ni chemin local.

Les données EuroVoc et EUR-Lex sont des données publiques réutilisables, avec mentions. Il n’y a ni fusion ni déploiement. **Le second dépôt reste privé jusqu’à votre ordre.**

## 7. Limites et risques

- **Qualification humaine absente.** Aucune donnée RAG n’a été relue. La validation à quatre yeux est obligatoire avant toute publication, quel que soit le résultat des contrôles automatiques.
- **Gain non mesuré.** Le bénéfice du RAG sur la traduction n’est pas mesuré ; le moteur cible n’est pas disponible.
- **Définitions UE et droit national.** Une définition légale de l’UE n’est pas toujours le terme du droit national applicable ; le relecteur doit le vérifier.
- **D-OPS-01.** La détection est a posteriori (délai dur + 120 s). Elle signale la perte mais ne la répare pas ; la reprise automatique reste à concevoir (Phase C).
- **D-DET-02.** La vérification lexicale peut envoyer en revue un bloc réellement français mais atypique (sigles, tableaux de chiffres). C’est voulu : un faux positif coûte une revue, une perte silencieuse coûte la fidélité.
- **CI.** La CI reste rouge sur les audits de dépendances (D-SUP-01), sans changement par rapport à la Phase A.

## 8. Décisions demandées

1. **Relecture et publication RAG.** Désigner les deux personnes (soumission et validation) pour les référentiels de la bibliothèque commune, et choisir les paires et les domaines à publier en premier.
2. **IATE.** Fournir un export TBX ciblé (domaines travail, banque et finance), obtenu avec votre compte EU Login, si vous souhaitez l’intégrer.
3. **D-ENG-01 et D-ENG-04.** Valeur cible du délai moteur et plafond de sortie, selon le moteur et le débit de production.
4. **Suite de la Phase B.** Ordre proposé : D-REC-01 (golden Surya avec tableau), D-REC-02, F-L2-02, D-SUP-01.
5. **LOT 3** (recherche juridique sur les textes EUR-Lex chargés) : non engagé sans votre validation explicite.
6. **Ouverture publique** du second dépôt : uniquement sur votre ordre.

**Production : NO-GO.** Rien dans cette phase ne lève ce statut. Il manque la licence écrite des poids Surya, la qualification humaine et documentaire, le moteur cible et les défauts critiques D-REC-02 et D-OPS-02.
