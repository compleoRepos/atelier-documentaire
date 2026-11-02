# LOT 2.3 — Rapport d’audit et mesure de référence (livrable 1, Phase A)

| | |
|---|---|
| Lot | LOT 2.3 — qualification qualité, performance et robustesse (crédit immobilier et consommation Maroc / MRE) |
| Phase | **A — audit, vérification du corpus et mesure de référence** (aucune modification du code produit) |
| Base auditée | branche `feature/ocr-surya-20261030`, tête `8351d83ffe0b` (PR brouillon n° 5, **non fusionnée**), sommet de la pile LOT 1 → LOT 2 → OCR Surya ; `main` inchangé |
| Date | 1er et 2 novembre 2026 |
| Statut | Phase A terminée ; **attente de votre validation explicite avant la Phase B** |
| Production | **NO-GO inchangé** (§12) |

> **Revue humaine.** Un humain valide chaque document, quel que soit le score. Rien dans ce rapport ne réduit cette revue.

### Statut des preuves (utilisé dans tout le rapport)

| Étiquette | Signification |
|---|---|
| **MESURÉ-S** | exécuté dans cet environnement sur un document **synthétique** du corpus (aucun document client) |
| **MESURÉ-P** | exécuté sur un document **public réel** du corpus (formulaire, modèle ou spécimen institutionnel ; **pas** une pièce de client remplie) |
| **LU** | constaté dans le code de la branche auditée (`fichier:ligne`) |
| **REPRIS** | chiffre d’un rapport antérieur, non remesuré dans cette phase |
| **ESTIMÉ** | calcul dérivé de mesures, non exécuté |
| **NON MESURÉ** | aucune donnée ; jamais remplacé par une estimation |

**Aucune mesure de ce rapport ne porte sur un document bancaire réellement rempli** : le corpus n’en contient pas, et aucun n’a pu être obtenu légalement (annexe A1). Les durées sont celles d’un **substitut CPU** du moteur de traduction (§1.3) ; elles ne sont pas transposables au moteur cible.

---

## 0. Synthèse

**Verdict.** La Phase A est terminée **sans aucune modification du code produit** (empreintes du code et des tests identiques avant et après). Le code audité passe ses tests. Il n’est pourtant **pas industriel** sur le chemin réel : avec un moteur de la classe mesurée, il ne traduit pas une page complète ; il peut omettre des blocs **en silence** ; il perd la tâche en cours dès qu’un worker s’arrête sans grâce suffisante, ce qui est le cas d’un simple déploiement avec les réglages livrés ; et le chemin OCR par défaut (Surya) n’a aucun golden. **Production : NO-GO.**

### Ce que la Phase A établit

| # | Constat | Gravité (ID) | Preuve |
|---|---|---|---|
| 1 | Délai moteur de 60 s **codé en dur**, non réglable : 6 appels sur 9 échouent ; les 7 appels d’une traduction complète (80,9 à 174,9 s) auraient tous échoué. Il faudrait au moins 133 jetons/s par requête. L’échec est visible (signalé), pas silencieux | Critique (D-ENG-01) | §3.4, §5.1 |
| 2 | **Perte silencieuse** : 15,5 à 16,7 % des blocs des PDF natifs sont étiquetés « français » ; sur D2, 23 blocs ne sont jamais envoyés au moteur, pour un seul signalement | Critique (D-DET-02) | §3.7, §9 |
| 3 | Un dossier de 14 pièces n’est **pas traduit en 2 heures** : 8 pièces sur 14 en revue ; 4 traductions de **1 page** tuées à 1 800 s, avec perte de tout leur travail ; une génération emballée (7 705 jetons en 1 293 s) a bloqué le moteur unique | Critique (D-OPS-02) ; Élevée (D-ENG-04) | §5.6 |
| 4 | Arrêt du worker : **4 arrêts sur 4** sans grâce suffisante, dont l’arrêt par défaut de Compose, laissent le document **figé** sans alerte ni reprise. Avec une grâce couvrant la tâche, Celery la termine correctement | Élevée (D-OPS-01) | §7 |
| 5 | Surya lit **une page à la fois** (deux scans simultanés : gain global de 4,1 %, second document +115 %) ; `OMP_THREAD_LIMIT=1` hérité le rend **3,27 fois plus lent sans message** ; le texte lu dépend du nombre de fils ; 52 à 122 s par page sur cette machine | Élevée (D-OCR-02, D-OCR-06) ; Moyenne (D-OCR-07) | §5.3, §6.1, §6.2 |
| 6 | Tableaux des PDF **natifs** : 214 signalements critiques de cellules traduites absentes du rendu, sur 5 pièces | Élevée (D-REC-03) | §5.6 |
| 7 | Deux étapes font 81 à 98 % du temps : le moteur (documents traduits) et l’OCR (scans). DICE prend moins de 0,15 s ; BM25 est hors du chemin (RAG DISABLED) ; le tokenizer, rechargé sans cache, coûte 3 à 4 s par document | Moyenne (D-PERF-TOK) | §5.7, §8 |

### Ce qui est reproduit

Les références du LOT 2.2 sont retrouvées, **sur le chemin réel** (API, Celery, Redis, S3) et non plus seulement dans un harnais : PDF natif de 5 pages en 689,3 s contre 689,6 s (au total, pas au détail, §5.2) ; Surya en première lecture à −0,7 % à +7,3 %, texte identique (§6.1) ; DICE à −5,7 % à +12,4 %, résultats identiques (§6.3) ; BM25 p50 de 26,7 à 35,1 ms contre 33,3 ms, mêmes résultats (§6.4).

### Tests et corpus

Suite backend : 1 031 tests réussis, et les 2 tests PostgreSQL ignorés réussissent sur une base réelle. Le golden (8 sur 8) force **Tesseract** : il ne couvre pas Surya (D-REC-01). La CI distante est **rouge** à cause de deux audits de dépendances (Pillow 12.3.0, `npm`) (livrable 9). Le corpus est conforme : 763 fichiers, aucun écart d’empreinte. Il ne contient **aucun document client rempli** (§4, annexe A1).

### Limites à garder en tête

- Le moteur de traduction mesuré est un **substitut CPU**. Le moteur cible n’a jamais été exécuté : aucun dimensionnement de production n’est possible à partir de ces chiffres.
- **Aucune qualification humaine** n’a eu lieu. Les références de traduction sont construites par le générateur, non vérifiées par un traducteur. La qualité de lecture et de traduction sera mesurée en Phase B ; la revue humaine reste obligatoire quel que soit le score.
- Trois erreurs de **mon outillage** sont déclarées. Le jeton de session non renouvelé (D-MES-02) a été compensé par une lecture directe en base ; le pilote reste à corriger avant toute campagne de plus d’une heure. Le mauvais port PostgreSQL et le premier essai d’arrêt non conforme (D-MES-03) ont été corrigés, et les mesures rejouées ; le premier essai d’arrêt est exclu.

**Décisions demandées** : §12. Aucune ligne de code produit ne sera modifiée avant votre validation explicite.

---

## 1. Méthode et périmètre

### 1.1 Règles respectées

- **Aucune modification du code produit.** L’empreinte du code et des tests est identique avant et après la phase (`044081dd76ff3690` / `18c5c9a842fa00ff`). Seuls des scripts de mesure **privés, hors dépôt** ont été écrits : instrumentation, pilotes, agrégations.
- **Corpus et golden non modifiés** : 763 fichiers contrôlés par empreinte SHA-256 (§4).
- **Aucun service externe** : aucun texte de document n’a quitté la machine. Le moteur de traduction et Surya tournent en local.
- **Tests existants exécutés avant les mesures** (livrable 9).
- **Synthétique et réel séparés** : chaque mesure porte son étiquette (tableau ci-dessus).

### 1.2 Chemin mesuré : le chemin réel, pas un harnais

La mesure de référence du LOT 2.2 (B0) appelait le pipeline **directement**, depuis un harnais. Elle ne passait ni par l’API, ni par Celery, ni par Redis, ni par le stockage S3. Surtout, ce harnais **imposait un délai moteur de 1 800 s**, alors que le produit applique **60 s** (§3.4). B0 ne mesurait donc pas le comportement réel du produit.

La Phase A mesure le **chemin réel** :

```
client HTTP → API (uvicorn, FastAPI) → validation, antivirus, stockage S3 chiffré, journal d’audit
            → file Celery « documents » (Redis) → worker Celery (2 processus, prefetch 1)
            → analyse (prétraitement, OCR Surya, langue, extraction) → document ANALYZED
            → POST /translate → worker → DICE / contexte → moteur de traduction → reconstruction
            → stockage du document final → contrôles → document REVIEW_REQUIRED (revue humaine)
```

Les commandes de lancement sont **identiques** à celles de Compose et de Helm : `uvicorn app.main:app` pour l’API, `celery -A app.workers.tasks worker --queues=documents --concurrency=2 --prefetch-multiplier=1` pour le worker. La base PostgreSQL 16 est migrée par Alembic (`0001` → `0004_rag_lot2`), et le compte de test est créé par l’outil d’amorçage du produit, sans écriture directe en base.

**Instrumentation externe, sans modification du code.** Des enveloppes sont installées au démarrage de chaque processus (signal Celery `worker_process_init` pour le worker, lanceur dédié pour l’API). Elles produisent des **traces corrélées par document et par tâche** : identifiant Celery, heure de publication, de début et de fin, temps mur, CPU du processus et de ses enfants, pic de mémoire, temps de chaque étape (inclusif et exclusif), et pour chaque appel au moteur ou à Surya : durée, jetons et minutages internes. **Aucun texte** n’est enregistré. Un échantillonneur relève chaque seconde le CPU et la mémoire (RSS et PSS) de chaque composant.

### 1.3 Écarts déclarés par rapport à une production

| Écart | Effet sur les chiffres |
|---|---|
| **Moteur de traduction = substitut** : gpt-oss-20b (MXFP4, 12,1 Go), llama.cpp b11700, **CPU 6 fils**, contexte 32 768, une requête à la fois. Le produit déploie un moteur **configurable** (Helm : service vLLM privé, tokenizer Qwen par défaut). | Le moteur cible n’a **jamais été exécuté** : aucun rapport de vitesse entre le substitut et la cible n’est connu (**NON MESURÉ**). Les durées de traduction servent à **localiser** les goulots et à tester la robustesse aux lenteurs, **pas** à dimensionner la cible. |
| Processus lancés **hors conteneurs**, sans limites cgroup (Compose : worker 2 CPU / 4 Go, API 2 CPU / 2 Go, Surya 4 CPU / 6 Go) ; réseau de l’hôte. | Pas de bridage CPU ni d’arrêt pour dépassement mémoire : les pics de mémoire sont **observés**, pas contraints. |
| Cœurs partagés : Surya cœurs 0 à 3 (4 fils, configuration du produit), moteur 6 fils sur 0 à 5, API et worker cœurs 4 et 5. | Le moteur et Surya se disputent les cœurs quand ils travaillent en même temps (cas réel d’un déploiement sur une seule machine). |
| Deux anciennes piles Compose de démonstration tournent sur la machine depuis trois semaines. Elles n’ont pas été arrêtées. | Leur consommation est relevée à part par l’échantillonneur (§5). |
| **Deux régimes de délai moteur** : *strict* (60 s, valeur du produit) et *délai 1 800 s* (surcharge déclarée par l’instrumentation, valeur de B0). | Le régime strict mesure le produit tel qu’il est ; le régime 1 800 s mesure ce que coûterait une traduction complète. |

## 2. Versions exactes

| Élément | Version |
|---|---|
| Code | `8351d83ffe0b` (auteur et committer Hamza NORDINE), 0 modification locale |
| Python / principales dépendances | Python 3.12.3 ; FastAPI 0.142.2 ; SQLAlchemy 2.1.3 ; Celery 5.6.3 ; redis-py 8.1.0 ; boto3 1.43.108 ; psycopg 3.3.6 ; PyMuPDF 1.28.2 ; Pillow 12.3.0 ; langdetect 1.0.9 ; httpx 0.28.1 |
| OCR | Surya OCR 2.5, poids GGUF **Q8_0** (628 680 096 octets) + projecteur (207 345 920 octets), llama.cpp b11700, 4 fils, cache de prompts désactivé (`--cache-ram 0`) — **licence des poids non validée par écrit** |
| Moteur de mesure (substitut) | gpt-oss-20b MXFP4 (12 109 566 624 octets), llama.cpp b11700, raisonnement « low » |
| Infrastructure de mesure | PostgreSQL 16, Redis 7.4 (mot de passe, AOF), MinIO (chiffrement côté serveur imposé par le stockage du produit) — conteneurs temporaires, volumes supprimés à la fin |
| Machine | 6 vCPU, 23 Go de RAM, disque à 93 % d’occupation |

## 3. Vérification des chemins réels d’exécution (LU)

### 3.1 Réception (API)

`POST /documents` enchaîne la validation (`validate_upload`), l’analyse antivirale (`scan_upload`), l’écriture sur le stockage, le journal d’audit, puis la mise en file de la tâche d’analyse. **L’antivirus est désactivé par défaut** (`av_scan_enabled = False` ; Compose : `TRANSLATOR_AV_SCAN_ENABLED:-false`), bien qu’un service ClamAV 1.4.3 soit déclaré dans Compose. La configuration de production l’exige : ce n’est donc pas un défaut en production, mais aucune mesure de la Phase A n’inclut le coût de l’antivirus. Le stockage S3 impose un chiffrement côté serveur (AES256).

### 3.2 Celery

| Paramètre | Valeur lue | Conséquence |
|---|---|---|
| Acquittement | à la **réception** (pas d’`acks_late`) | une tâche prise par un worker qui meurt est **retirée de la file** : risque de perte, mesuré au §7 |
| `reject_on_worker_lost`, reprise automatique | absents | aucune relance automatique d’une tâche interrompue |
| Délais | 1 800 s (souple) / 1 860 s (dur), **par tâche** | un gros document peut dépasser le délai (§5) |
| Préchargement | 1 tâche par processus | équité correcte entre documents |
| Concurrence | 2 processus | 2 documents traités en parallèle par worker |
| Démarrage de chaque tâche | création du moteur, contrôle du schéma de base (`init_db`), création du stockage | coût fixe par tâche (§5) |

### 3.3 OCR

Le moteur par défaut est **Surya**, joint par HTTP. Il n’existe aucun repli silencieux vers Tesseract : si Surya est injoignable, le document échoue avec un code explicite. Le service traite **une page à la fois** ; deux documents simultanés s’attendent donc l’un l’autre.

### 3.4 Traduction : délai moteur de 60 s (constat D-ENG-01, nouveau)

- `app/ai/translation/service.py:1039` : le moteur privé est créé avec `timeout=options.get("timeout", 60.0)`.
- `app/application/jobs.py` (`run_translate`) ne transmet **aucun** délai, et aucun réglage (`Settings`) ne le permet : le délai effectif est **toujours 60 s**.
- L’appel HTTP n’est pas en flux : le client attend la réponse **complète**. Tout appel de plus de 60 s échoue (`PRIVATE_GATEWAY_FAILED`, critique).
- Ce code ne fait pas partie des codes qui déclenchent un redécoupage de la requête (`_SPLIT_CODES` : dépassement de contexte, sortie invalide). Les blocs concernés restent donc en langue source, marqués non traduits. **L’échec est visible** : signalement critique, document mis en revue. Il n’est pas silencieux.
- **Arithmétique indépendante du moteur** : le budget de sortie est de 8 000 jetons par requête. Pour qu’une sortie de taille maximale aboutisse en 60 s, il faut **au moins 133 jetons/s par requête**. C’est une incohérence de configuration, vraie quel que soit le matériel.

### 3.5 Tokenizer rechargé à chaque document (constat D-PERF-TOK, nouveau, confirmé par mesure)

`translate_blocks` (`service.py:942`) crée un moteur à **chaque** document. Ce moteur recharge le tokenizer depuis le disque (`_load_local_tokenizer`, `service.py:352`, `AutoTokenizer.from_pretrained`, sans cache) et recalcule l’empreinte de ses fichiers. Mesure dédiée : §8.

### 3.6 DICE et BM25

Le mode RAG est **DISABLED** par défaut. Sur le chemin d’un document, seul le constructeur de contexte s’exécute (contexte voisin, prompt). La partie terminologique de DICE et la recherche BM25 **ne s’exécutent pas** : BM25 n’est appelé que par l’API de suggestion. Les deux composants sont donc mesurés par un banc séparé (§6).

### 3.7 Contrôles et omission masquée (rappel D-DET-02)

`jobs.py:490-525` retire les signalements « non traduit » des blocs que le détecteur a étiquetés **français**. Un bloc étranger mal étiqueté « français » n’est donc **ni traduit, ni signalé**. Le défaut est connu depuis le LOT 2.2 ; la Phase A en mesure la fréquence sur le chemin réel (§5).

## 4. Vérification du corpus (MESURÉ) : conforme

| Contrôle | Résultat |
|---|---|
| Intégrité | 763 fichiers du manifeste contrôlés par SHA-256 : **0 absent, 0 divergent, 0 fichier hors manifeste** |
| Documents synthétiques uniques | **513** (consigne : 513) ; plus 3 doublons volontaires (tests de détection de doublons) |
| Variantes dégradées | **116** (consigne : 116) |
| Documents publics réels ou modèles institutionnels | **127** (consigne : 127) ; plus 3 en quarantaine, hors corpus |
| Documents synthétiques de tiers | 4 (reclassés au LOT précédent ; ce ne sont pas des documents réels) |
| Dossiers complets synthétiques | **23** : **13** immobiliers, **10** consommation (consigne : 23 / 13 / 10) ; 21 anomalies injectées ; 7 dossiers témoins sans anomalie |
| Documents de référence | **53** synthétiques (consigne : 53), plus 9 documents réels avec texte source uniquement |
| Blocs à traduire / valeurs à conserver | **918** / **2 308** (consigne : 918 / 2 308) ; références **construites, non vérifiées par un humain** |
| Pages | 3 437 au total ; dossiers de 11 à 38 pages |

**Limite rappelée.** Les 127 documents réels sont des formulaires, modèles et spécimens. **Aucun n’est une pièce de client remplie**, et le corpus ne contient **aucun relevé bancaire réel**. Les traductions de référence sont construites automatiquement à partir du générateur, et non validées par un traducteur.

## 5. Mesure de référence sur le chemin réel (campagne A)

Tous les documents sont soumis par l’API, un par un (mode « série ») ou ensemble (mode « lot »). Le document est ensuite suivi jusqu’à son état final. Chaque mesure est **MESURÉ-S** (banc synthétique du LOT 2.2 ou corpus), sauf D8 (**MESURÉ-P**).

### 5.1 Régime strict (le produit tel qu’il est) : D-ENG-01 confirmé

| Mesure | Document | Bout en bout | Appels moteur | Durée des appels | Blocs signalés « non traduits » | Statut final |
|---|---|---:|---|---|---:|---|
| S1 | PDF natif, 1 page, 30 blocs | 71,2 s | 1 : **0 réussi, 1 échoué** | échec à 60,1 s | 9 | revue requise |
| S2 | PDF natif, 5 pages, 148 blocs | 387,7 s | 7 : **3 réussis, 4 échoués** | réussis 57,4 / 55,6 / 20,0 s ; échecs à 60,1 s (240,4 s perdus) | 42 | revue requise |
| S3 | scan moyen, 1 page, 21 blocs | 137,6 s (dont OCR 60,6 s) | 1 : **0 réussi, 1 échoué** | échec à 60,1 s | 8 | revue requise |

**Constat (MESURÉ-S).** Avec le moteur de mesure, **6 appels sur 9 échouent** au délai de 60 s. Les 3 appels réussis sont les plus petits, et deux d’entre eux réussissent de justesse (57,4 s et 55,6 s). En régime 1 800 s (§5.2), les 7 appels nécessaires à une traduction complète durent **de 80,9 à 174,9 s** : **tous** auraient échoué en régime strict.

L’échec est **visible** : signalement critique `PRIVATE_GATEWAY_FAILED`, blocs restés en langue source signalés « non traduits », document mis en revue. Le moteur annule proprement chaque requête abandonnée (journal du moteur : « cancel task »), sans effet de cascade : la requête suivante est servie en moins d’une seconde. Le travail déjà calculé est en revanche perdu (845 à 1 299 jetons par appel annulé).

**Lecture.** Le produit, tel qu’il est livré, ne traduit pas une page complète avec un moteur de cette classe. Il faudrait **au moins 133 jetons/s par requête** pour garantir la sortie maximale autorisée (8 000 jetons) en 60 s. Le moteur de mesure génère **5,5 à 7,5 jetons/s**. Le moteur cible n’ayant jamais été exécuté, on ne sait pas s’il atteint ce débit (**NON MESURÉ**).

### 5.2 Régime 1 800 s (traduction complète) : comparaison avec B0

Même pile, même moteur. Seul le délai moteur est porté à 1 800 s, valeur imposée par le harnais B0. Le chemin mesuré est réel (API, Celery, Redis, S3), ce qui n’était pas le cas de B0.

| Mesure | Document | Étapes | Bout en bout (chemin réel) | B0 (harnais, LOT 2.2) | Écart |
|---|---|---|---:|---:|---:|
| D1 | PDF natif, 1 page | analyse + traduction | 143,0 s | 134,0 s | +6,7 % |
| D2 | PDF natif, 5 pages | analyse + traduction | 689,3 s | 689,6 s | 0,0 % |
| D3 | scan moyen, 1 page | analyse + traduction | 120,1 s | 149,6 s | **non comparable** (artefact, ci-dessous) |
| D4 | scan moyen, 5 pages | analyse seule | 316,1 s | 296,9 s | +6,5 % |
| D5 | DOCX 10 pages | analyse seule | 6,6 s | 5,5 s | +1,1 s |
| D5 | XLSX 10 feuilles | analyse seule | 4,3 s | 3,2 s | +1,1 s |
| D5 | PPTX 10 diapositives | analyse seule | 4,3 s | 3,0 s | +1,3 s |
| D5 | PDF natif 10 pages | analyse seule | 4,5 s | 2,6 s | +1,9 s |

**D2 : total reproduit, détail différent (MESURÉ-S).** Le total est identique à 0,3 s près, et le moteur pèse 97,9 % du temps dans les deux mesures. Mais la composition diffère : D2 fait 5 appels (4 840 jetons en entrée, dont 1 990 servis par le cache du moteur ; 3 232 jetons générés ; 5,7 jetons/s en génération), B0 en faisait 8 (6 227 en entrée ; 3 579 générés ; 6,9 jetons/s). La référence est donc reproduite **au total, pas au détail**. Le débit de génération baisse au fil de la campagne : 7,5 puis 6,5 jetons/s en régime strict, puis 5,5 à 5,9 jetons/s sur les 7 appels du régime 1 800 s. La cause de cette baisse **n’est pas établie**. Les hypothèses (contexte cumulé, concurrence CPU des piles de démonstration) ne sont pas démontrées.

**D3 : artefact de mesure découvert.** L’OCR de D3 dure 18,7 s, contre 60,6 s pour **la même page** en S3. Surya a servi la même image deux fois de suite, et llama.cpp a réutilisé une partie du calcul précédent (journal du service : 58,7 s puis 16,8 s). Ce n’est **pas** une performance du produit. En usage réel, deux pages identiques consécutives sont rares. D3 est donc écarté des comparaisons de durée OCR. La campagne B a été corrigée en conséquence (pages différentes à chaque répétition). Le même contrôle a été fait sur D6 : la première page de D6b diffère de la dernière de D6a, D6 n’est donc pas touché.

**Formats bureautiques (MESURÉ-S).** Le chemin réel ajoute **1,1 à 1,9 s par document** au harnais. Ce surcoût fixe vient de la réception, de la mise en file, du démarrage de la tâche (création du moteur, contrôle du schéma de base, création du stockage) et de l’intervalle de suivi du client. Il est négligeable devant l’OCR et la traduction, mais pas devant l’analyse d’un document natif (4 à 7 s).

### 5.3 Concurrence : deux scans simultanés (D6, MESURÉ-S)

Deux variantes « scan dégradé » du corpus (1 page chacune ; 96 et 52 blocs), en série puis en lot. Le worker a 2 processus : les deux documents démarrent donc ensemble.

| | Série (D6a) | Lot (D6b) | Écart |
|---|---:|---:|---:|
| Document 1 (96 blocs) | 116,2 s | 114,6 s | −1,4 % |
| Document 2 (52 blocs) | 93,2 s | 200,8 s | **+115 %** |
| Durée individuelle moyenne | 104,7 s | 157,7 s | **+50,7 %** |
| Durée totale des deux | 209,7 s | 201,0 s | **gain de 4,1 %** |

**Cause (MESURÉ-S).** Surya traite **une page à la fois** (barrière du service). Le second document attend environ 101 s que la page du premier soit lue, puis il est lu à son tour en 84 s environ. Le traitement en parallèle ne fait donc gagner que les étapes hors OCR.

**Comparaison avec le LOT 2.2.** Le constat est confirmé sur la version actuelle, avec des chiffres du même ordre : gain global de 4,1 % (LOT 2.2 : 7,8 %), allongement individuel de 51 % en moyenne et de 115 % pour le second document (LOT 2.2 : 67 à 81 %). Les protocoles diffèrent (documents différents, chemin réel au lieu du harnais) : les chiffres ne sont pas directement comparables, mais la conclusion est la même. **Avec un seul service Surya, deux workers n’apportent quasiment aucun débit sur les scans.**

**Durée OCR des scans du corpus.** Les scans dégradés du corpus demandent 83 à 104 s par page, contre 52,5 à 55,6 s pour les scans du banc LOT 2.2 (D4). Leur contenu est plus dense (96 blocs sur une page contre 20 en moyenne). Cela rejoint la moyenne de 89,5 s par page mesurée sur l’échantillon OCR du corpus lors de sa construction (REPRIS), et les 71 à 120 s par page des pages du corpus rejouées en B1 (§6.1).

### 5.4 Variantes dégradées du corpus (D7, MESURÉ-S, analyse seule)

Cinq variantes de 1 page, issues de deux sources du corpus (espagnole et néerlandaise), envoyées en série. Total : 526,9 s.

| Variante (source) | Bout en bout | Dont OCR Surya | Blocs | Langue détectée |
|---|---:|---:|---:|---|
| photo de smartphone (ES) | 129,2 s | 119,1 s | 85 | espagnol |
| forte inclinaison (ES) | 126,9 s | 115,6 s | 78 | espagnol |
| compression forte (ES) | 100,5 s | 90,6 s | 38 | espagnol |
| fax basse résolution (BE) | 84,4 s | 77,4 s | 38 | néerlandais |
| scan propre (BE) | 85,0 s | 76,7 s | 32 | néerlandais |

**Lecture.** L’OCR représente 90 à 92 % du temps d’analyse. Une même source donne 38 à 85 blocs selon la dégradation (52 en « scan dégradé », D6) : le découpage en blocs dépend de la qualité de l’image. La qualité de lecture elle-même n’est pas mesurée ici (Phase B). Surya reçoit aussi de petites requêtes (recadrages de 43 000 à 110 000 pixels, 1,8 à 3,8 s chacune), pour la vérification de lignes, en plus de la page entière.

**Observation D-OBS-01.** Le scan propre et le fax basse résolution reçoivent **exactement les mêmes codes de signalement**, dont `OCR_ORIENTATION_NOT_CHECKED`. Les signalements ne distinguent donc pas une entrée dégradée d’une entrée propre. C’est une observation, pas un défaut prouvé : rien n’établit ici que la lecture du fax est moins bonne.

### 5.5 Document public réel (D8, MESURÉ-P)

Spécimen public d’avis de pension allemand (`REEL-DE-007`), 1 page scannée, analyse puis traduction, régime 1 800 s.

| Étape | Durée | Détail |
|---|---:|---|
| Analyse (OCR Surya compris) | 140,9 s | 40 blocs, 1 795 caractères, 1 tableau, langue allemande |
| Traduction | 646,9 s | 7 appels, tous réussis ; 4 800 jetons en entrée, 2 610 générés |
| **Bout en bout** | **790,7 s** | statut final : **revue requise** |

Signalements : 78 erreurs, 72 avertissements, 1 information. Les plus nombreux sont `PROTECTED_TRANSLATION_NOT_APPLIED` (79) et `UNPROTECTED_ENTITY_REQUIRES_REVIEW` (58). Tous sont **visibles** et envoient le document en revue.

**Observation D-CLS-01 (à confirmer).** Le document est classé `invoice` (facture), domaine finance, alors que c’est un avis de pension. **Aucun signalement** ne relève cette erreur de classement. Un seul exemple ne suffit pas à établir un défaut. L’effet sur le glossaire et le contexte de traduction n’est pas mesuré.

### 5.6 Dossier complet de 14 pièces (D9, MESURÉ-S)

Dossier synthétique de crédit à la consommation (MRE résidant en Allemagne, `CONSO-C8-DE`) : 14 PDF natifs, 16 pages, sans OCR. Les pièces 01 à 11 sont en allemand, les pièces 12 à 14 (formulaire, simulation et offre de crédit) en français. Les 14 pièces sont envoyées ensemble, puis traduites. Conditions : régime 1 800 s, worker à 2 processus, **un seul moteur** servant une requête à la fois.

**Défaut de mesure déclaré (mon pilote, pas le produit).** Le jeton de session du produit expire au bout de **60 minutes** (`jwt_expire_minutes = 60`). Mon pilote ne le renouvelait pas : passé ce délai, il n’a plus lu aucun état, puis s’est arrêté à sa propre limite de 2 heures. Les statuts ci-dessous sont donc lus **directement en base** (lecture seule, base temporaire de mesure). Ils ne viennent pas du pilote.

| Pièces | Attente en file avant traduction | Durée de traduction | Appels (réussis) | Statut réel | Signalements |
|---|---:|---:|---|---|---:|
| 01 bulletin de salaire | 0 s | **1 800 s (tuée)** | 17 (16) | **échec** | 1 |
| 02 bulletin de salaire | 4 s | 1 603 s | 14 (14) | revue requise | 201 |
| 03 bulletin de salaire | 1 607 s | **1 800 s (tuée)** | 18 (17) | **échec** | 1 |
| 04 contrat de travail | 1 800 s | 1 545 s | 15 (15) | revue requise | 162 |
| 05 attestation employeur | 3 346 s | 332 s | 3 (3) | revue requise | 82 |
| 06 avis d’imposition | 3 407 s | 369 s | 3 (3) | revue requise | 143 |
| 07 certificat annuel de revenus | 3 678 s | 476 s | 4 (4) | revue requise | 89 |
| 08 relevé bancaire | 3 776 s | **1 800 s (tuée)** | 5 (4) | **échec** | 1 |
| 09 relevé bancaire | 4 153 s | **1 800 s (tuée)** | 6 (5) | **échec** | 1 |
| 10 relevé bancaire | 5 573 s | 1 021 s | 7 (7) | revue requise | 205 |
| 11 justificatif de domicile | 5 950 s | 575 s | 3 (3) | revue requise | 108 |
| 12 formulaire de demande de crédit | 6 528 s | interrompue | 4 (3) | **bloqué en « traduction »** | 1 |
| 13 simulation de crédit | 6 597 s | 485 s | 2 (2) | revue requise | 29 |
| 14 offre de crédit (3 pages) | 7 080 s | interrompue | 1 (0) | **bloqué en « traduction »** | 1 |

**Ce que montre D9.**

1. **Le dossier n’est pas traduit en 2 heures.** Seules 8 pièces sur 14 arrivent en revue. L’analyse est rapide (0,2 à 3,4 s par pièce) ; tout le temps passe dans la traduction et dans l’attente du moteur. L’attente en file médiane est de 3 727 s (maximum 7 080 s). La traduction médiane est de 844 s par pièce, et l’appel réussi médian dure 104,8 s.
2. **D-OPS-02 confirmé sur le chemin réel, dès une page.** Quatre traductions de **1 page** atteignent la limite de tâche de 1 800 s (`SoftTimeLimitExceeded`). Le document passe en **échec** avec un seul signalement `TRANSLATION_FAILED` : l’échec est visible, mais **tout le travail déjà fait est perdu**, y compris les appels réussis. Cause : les deux processus du worker se partagent un moteur qui sert une requête à la fois, si bien que chaque tâche attend aussi les appels de l’autre.
3. **Coût très inégal selon le type de pièce.** Un bulletin de salaire demande 14 à 18 appels (7 500 à 8 500 jetons en entrée) ; un relevé, 5 à 7 ; les autres pièces, 1 à 4. Le bulletin, pièce la plus fréquente d’un dossier, est aussi la plus chère à traduire.
4. **Génération emballée (D-ENG-04, nouveau).** Pendant D9, une requête a généré **7 705 jetons en 1 293 s**, tout près du plafond fixe de 8 000. Elle a ensuite été annulée par la limite de tâche. Pendant ce temps, l’appel de l’autre processus a **attendu 1 315 s** avant d’être servi, en 21 s. C’est 1 requête sur 119 dans toute la campagne A ; la suivante en taille générait moins de 2 500 jetons (médiane 845). La cause n’est **pas établie**, car le contenu n’est pas journalisé. Une boucle de répétition est probable, non démontrée. Avec un moteur à une seule file, une seule requête de ce type bloque tous les documents pendant près de 24 minutes à ce débit.
5. **Documents bloqués après un arrêt (illustration de D-OPS-01).** En fin de campagne, mon script a arrêté le worker en envoyant SIGTERM à **tous** ses processus, y compris ceux qui exécutaient les tâches. Ce n’est pas l’arrêt « à chaud » prévu par Celery, qui laisse finir les tâches en cours. Les deux tâches en cours sont perdues (`WorkerLostError`), et les pièces 12 et 14 restent **indéfiniment** au statut « traduction », sans erreur, sans reprise et sans signalement. Les essais d’arrêt formels sont au §7.
6. **Référence qualité avant la Phase B** (8 pièces en revue, 8 pages, PDF natifs, sans OCR). Signalements critiques : `PDF_TABLE_CELL_TARGET_MISSING` 214 (5 pièces), `LAYOUT_OVERFLOW` 36 (5), trois codes de texte manquant au rendu (14 chacun, 7 pièces), `PROTECTED_REGION_CHANGED` 12 (2), `PROTECTED_ENTITY_CHANGED` 5 (2). Erreurs : `PROTECTED_TRANSLATION_NOT_APPLIED` 60 (7), `UNTRANSLATED` 39 (8), `TABLE_AMBIGUOUS_CELL_LINK` 24 (2), `PDF_CELL_SOURCE_TEXT_UNMAPPED` 20 (1), `QUALITY_THRESHOLD_NOT_MET` 13 (8), `VISUAL_GEOMETRY_REGRESSION` 8 (8). Tous sont **visibles**. Ils montrent que les **tableaux des PDF natifs**, et pas seulement ceux des scans (D-REC-02), perdent des cellules traduites. Ce point est à qualifier visuellement en Phase B.

**Conditions.** Pendant D9, la mémoire de la machine était occupée à 21,3 Go sur 24,4 (moteur : 14,4 Go résidents). Le moteur relisait son modèle depuis le disque à environ 21 Mo/s, et générait 5,5 jetons/s contre 7,5 en début de campagne. Le lien entre pression mémoire et baisse de débit est une **hypothèse non démontrée**.

### 5.7 Les 11 étapes demandées, en temps exclusif (MESURÉ-S/P)

Chaque durée est le **temps propre** de l’étape : le temps passé dans ses sous-étapes n’y est pas recompté, ce qui permet d’additionner les lignes. Le « CPU worker » est une estimation (temps processeur du processus pendant l’étape). L’OCR et la traduction se passent surtout **hors** du worker, dans Surya et dans le moteur : leur CPU worker est donc faible. Le tableau détaillé (moyenne, p50, p90, p95, maximum, CPU et pic RSS, pour chaque mesure) est dans les sorties privées de mesure. Voici quatre profils représentatifs.

| Étape | D2 natif 5 p., traduit | D4 scan 5 p., analyse seule | D8 réel 1 p., traduit | D9 par pièce (moy. / p95) |
|---|---:|---:|---:|---:|
| 1. Réception et validation | 0,04 s | 0,11 s | 0,06 s | 0,05 / 0,05 s |
| 2. Prétraitement d’image | 0,03 s | 19,75 s | 4,23 s | 0,01 / 0,03 s |
| 3. Détection de langue | 0,58 s | 0,75 s | 0,13 s | 0,22 / 0,37 s |
| 4. OCR (Surya) | — | **277,61 s** | **134,17 s** | — |
| 5. Extraction et normalisation | 0,90 s | 14,61 s | 2,10 s | 0,46 / 1,13 s |
| 6. Contexte (DICE) | 0,04 s | — | 0,03 s | 0,05 / 0,13 s |
| 7. Recherche BM25 | 0 (RAG désactivé) | 0 | 0 | 0 |
| 8. Traduction (moteur) | **674,74 s** | — | **641,71 s** | **1 021,5 / 1 796,5 s** |
| 9. Reconstruction | 2,20 s | — | 0,13 s | 0,33 / 0,97 s |
| 10. Génération du document final | 1,20 s | 0,58 s | 0,50 s | 0,35 / 0,62 s |
| 11. Contrôles et validation | 2,51 s | — | 0,60 s | 1,46 / 4,50 s |
| Orchestration non détaillée | 4,76 s | 0,87 s | 4,17 s | 4,00 / 5,48 s |
| **Total de bout en bout** | **689,4 s** | **316,4 s** | **790,8 s** | voir §5.6 |
| Part de l’étape dominante | moteur 97,9 % | OCR 87,8 % | moteur 81,2 % | moteur |
| Pic de mémoire du worker | 796 Mo | 1 006 Mo | 1 125 Mo | 1 114 Mo |

**Lecture.**

1. **Deux étapes seulement comptent.** La traduction par le moteur (documents traduits) et l’OCR (scans) font 81 à 98 % du temps. Toutes les autres étapes réunies restent sous 30 s par document. Optimiser ailleurs, y compris DICE (moins de 0,15 s) ou BM25 (désactivé), ne changera pas la durée perçue.
2. **Le prétraitement d’image d’un scan n’est pas négligeable** : 19,7 s pour 5 pages, soit environ 4 s par page, entièrement dans le worker (CPU 23,6 s, donc plusieurs fils).
3. **L’orchestration non détaillée** (4 à 5 s par document traduit) est surtout la préparation des blocs à traduire (`traduction.blocs`, 3,2 à 3,8 s). Cela correspond au rechargement du tokenizer à chaque document (D-PERF-TOK, mesure isolée au §8).
4. **Moteur pendant D9.** 102 appels, 53 790 jetons en entrée (dont 19 763 servis par le cache du moteur), 27 629 générés. Le préremplissage a pris 1 289 s (26,4 jetons/s) et la génération 4 539 s (6,1 jetons/s). Le moteur a donc été occupé environ **81 %** des 2 heures : le dossier est limité par le moteur, pas par l’application.
5. **Mémoire du worker** : le pic va de 0,8 à 1,1 Go **par processus**. Avec 2 processus et le processus maître, cela fait environ 2,3 à 2,5 Go (ESTIMÉ), sous la limite de **4 Go et 2 CPU** fixée par Compose (`WORKER_MEMORY_LIMIT`) comme par Helm. La marge restante ne couvre pas avec certitude un document de 200 pages, qui n’a pas été mesuré. La limite de 2 CPU pèse aussi sur le prétraitement d’image, qui utilise plusieurs fils.

## 6. Références des composants (campagne B)

Chaque mesure est répétée **trois fois**. Les composants sont appelés directement, hors pipeline : Surya par HTTP, DICE et BM25 par les bancs du LOT 2.2 rejoués sans modification. Les entrées sont synthétiques (MESURÉ-S), sauf la page `REEL-DE-003`, formulaire public réel (MESURÉ-P).

### 6.1 Surya : reproduction des références et effet du cache (B1)

Six pages (trois du banc LOT 2.2, trois du corpus), deux configurations :

- **configuration de référence** : celle des mesures antérieures (5 fils, cache de prompts de llama.cpp laissé à sa valeur par défaut) ;
- **configuration du produit** : point d’entrée du service, 4 fils, cache de prompts désactivé (`--cache-ram 0`).

Le F1 est calculé par l’outil d’évaluation des mesures antérieures, contre la vérité terrain de la page.

| Page (origine) | Référence antérieure | Config. de référence, rép. 1 | Écart | Config. de référence, rép. 2 / 3 | Config. du produit, moy. (min–max) | Écart produit / référence | F1 réf. / produit |
|---|---:|---:|---:|---:|---:|---:|---|
| `en-moyen-p1` (banc) | 48,3 s | 47,97 s | −0,7 % | 14,63 / 14,80 s | 53,72 s (51,90–55,90) | +11,2 % | 1,0 / 1,0 |
| `lang-de-p1` (banc) | 46,5 s | 47,97 s | +3,2 % | 16,36 / 15,80 s | 54,19 s (52,92–54,85) | +16,5 % | 1,0 / 1,0 |
| `lang-ar-p1` (banc) | 50,6 s | 51,16 s | +1,1 % | 19,77 / 20,29 s | 57,85 s (57,46–58,14) | +14,3 % | **0,8219 / 0,8299** |
| `SYN-IMMO-P8-DE-11`, p. 1 (corpus) | 61,3 s | 65,79 s | +7,3 % | 28,62 / 31,20 s | 71,02 s (70,26–72,07) | +15,9 % | 0,9946 / 0,9946 |
| `OCR-CONSO-C4-ES-06`, scan dégradé, p. 1 (corpus) | 71,1 s | 73,44 s | +3,3 % | 39,20 / 38,71 s | 83,49 s (82,52–83,99) | +17,4 % | 0,9096 / 0,9096 |
| `REEL-DE-003`, p. 1 (corpus, public réel) | 106,4 s | 106,96 s | +0,5 % | 77,20 / 78,33 s | 119,90 s (117,85–121,90) | +12,7 % | 0,9765 / 0,9765 |
| **Moyenne par page** | — | **65,55 s** | — | 32,63 / 33,19 s | **73,36 s** (rép. 74,12 / 73,14 / 72,82) | +11,9 % | — |

Aucune erreur HTTP sur les 36 lectures. Configuration du produit, 18 lectures : p50 64,2 s, p95 120,2 s, maximum 121,9 s ; coefficient de variation par page de 0,5 à 3,1 %.

**Lecture.**

1. **Les références antérieures sont reproduites**, en première lecture : écarts de −0,7 % à +7,3 %, et texte lu identique (F1 identique sur les 6 pages).
2. **Le cache de prompts biaise toute mesure répétée (extension de D-MES-01).** Avec le cache par défaut, les répétitions 2 et 3 d’une page sont **1,4 à 3,3 fois plus rapides** que la première, même quand d’autres pages ont été lues entre-temps. Le gain est le plus fort sur les pages les moins denses. Une moyenne sur plusieurs répétitions dans cette configuration serait donc fausse ; les références antérieures restent valides, car prises en première lecture. La configuration du produit désactive ce cache, et ses trois répétitions sont stables. Il reste la réutilisation d’une image **identique et immédiatement consécutive** (D3, §5.2), observée elle aussi dans la configuration du produit.
3. **La configuration du produit est 11 à 17 % plus lente par page** que la configuration de référence (4 fils au lieu de 5). Les durées d’OCR du chemin réel (§5) sont celles de la configuration du produit, et elles concordent avec B1 : 52,5 à 55,6 s par page pour les scans du banc (D4), contre 53,7 à 57,9 s ici.
4. **D-OCR-07 (nouveau, observation).** Sur la page arabe, le texte lu **change avec le nombre de fils** (F1 0,8219 avec 5 fils, 0,8299 avec 4), alors qu’il est identique d’une répétition à l’autre dans une même configuration. Un golden sur le chemin Surya (D-REC-01) devra donc fixer le nombre de fils et la quantification. Sinon, il échouera sans régression réelle, ou masquera une régression réelle derrière une tolérance trop large.

### 6.2 Surya : variable `OMP_THREAD_LIMIT=1` héritée (B2)

Vrai point d’entrée du service, configuration du produit, trois pages différentes, chacune lue avec et sans la variable.

| Page | Sans limite | Avec `OMP_THREAD_LIMIT=1` | Facteur |
|---|---:|---:|---:|
| `en-moyen-p1` | 58,49 s | 189,97 s | ×3,25 |
| `lang-de-p1` | 53,87 s | 177,43 s | ×3,29 |
| `lang-ar-p1` | 55,81 s | 182,51 s | ×3,27 |

**D-OCR-06 confirmé (MESURÉ-S).** Facteur moyen **×3,27** (LOT 2.2 : ×3,07). Les six lectures répondent HTTP 200 : le ralentissement ne produit **aucun message, aucune erreur, aucun signalement**. Un exploitant qui reprend l’ancienne convention de déploiement (une variable utile à Tesseract) triple la durée de l’OCR sans le savoir. Avec ce facteur, l’analyse d’un scan de 5 pages passerait d’environ 5 minutes à plus de 15 (ESTIMÉ), et un scan d’environ 9 pages atteindrait le délai de tâche de 1 800 s (ESTIMÉ, D-OPS-02).

### 6.3 DICE : constructeur de contexte terminologique (B3)

Banc du LOT 2.2, 100 blocs par document, mémoires de 200, 2 000 et 20 000 entrées. Durée de préparation du plan par document.

| Entrées | B0 (LOT 2.2) avec cache | B3 avec cache, 3 rép. | B0 sans cache | B3 sans cache, 3 rép. | Clés appariées / sélectionnées (B0 = B3) |
|---:|---:|---:|---:|---:|---|
| 200 | 51,95 ms | 51,04 – 54,99 ms | 61,39 ms | 60,95 – 65,47 ms | 42 / 15 |
| 2 000 | 53,17 ms | 53,97 – 57,29 ms | 153,41 ms | 157,49 – 172,35 ms | 154 / 16 |
| 20 000 | 62,27 ms | 61,52 – 68,78 ms | 1 291,17 ms | 1 217,41 – 1 377,36 ms | 588 / 16 |

**Lecture (MESURÉ-S).** La référence est reproduite : écarts de −5,7 % à +12,4 % selon la mesure, et **résultats strictement identiques** à B0 (mêmes clés appariées, mêmes entrées sélectionnées) dans les trois répétitions. Le coût est dominé par l’appariement (44 à 55 ms par document, quelle que soit la taille de la mémoire). La construction de l’index ne pèse qu’en l’absence de cache : environ 1,3 s pour 20 000 entrées, une fois. Rappel : sur le chemin d’un document, DICE terminologique **ne s’exécute pas** tant que le mode RAG reste DISABLED (§3.6, §5.7) ; ces chiffres sont une référence pour la Phase C, pas un coût actuel.

### 6.4 BM25 sur PostgreSQL 16 (B3)

Banc du LOT 2.2 : 20 000 entrées (58 475 lignes d’index inversé, table de 19 Mo), publication, puis 300 requêtes ; base dédiée et jetable à chaque répétition.

| Mesure | B0 (LOT 2.2) | Rép. 1 | Rép. 2 | Rép. 3 |
|---|---:|---:|---:|---:|
| Ajout des 20 000 entrées | 9,38 s | 10,36 s | 9,35 s | 9,94 s |
| Publication et index | 9,13 s | 9,43 s | 9,18 s | 9,33 s |
| Requêtes avec résultat | 297 / 300 | 297 / 300 | 297 / 300 | 297 / 300 |
| Latence p50 | 33,32 ms | 32,88 ms | 26,68 ms | 35,09 ms |
| Latence p95 | 49,14 ms | 51,50 ms | 39,57 ms | 43,31 ms |
| Latence maximale | 55,45 ms | 69,43 ms | 50,31 ms | 61,27 ms |
| Index utilisé par le plan d’exécution | oui | oui | oui | oui |

**Lecture (MESURÉ-S).** Référence reproduite, mêmes résultats de recherche (297 requêtes sur 300 avec résultat). BM25 n’est **pas** sur le chemin d’un document : il ne sert que l’API de suggestion (§3.6).

**Défaut de mon outillage, déclaré et corrigé.** La première exécution de ce banc, et celle des tests PostgreSQL (livrable 9, §7), n’ont **jamais démarré** : mon script lançait `psql` dans le conteneur sans préciser le port et visait donc le port par défaut, alors que la base temporaire écoute sur un autre port. Le script a été corrigé et les deux mesures rejouées ; les chiffres ci-dessus viennent de la reprise.

## 7. Robustesse : arrêt du worker pendant une tâche (B4)

Le worker est arrêté **pendant l’OCR** d’un scan de la banque d’essai LOT 2.2 (1 ou 5 pages). Aucune image n’est lue deux fois de suite par Surya, qui a en outre été relancé entre la campagne initiale et la reprise : aucune réutilisation de calcul ne fausse les essais. On relève ensuite la file Redis (messages en attente et non acquittés), le statut du document **en base** (lecture seule) et le comportement après relance du worker. Les commandes de lancement sont celles de Compose et de Helm : le processus maître de Celery est le processus principal du conteneur, et c’est à lui seul que l’orchestrateur envoie le signal d’arrêt.

**Lu dans la branche auditée** : aucune durée de grâce d’arrêt n’est fixée, ni dans Compose (`stop_grace_period`) ni dans Helm (`terminationGracePeriodSeconds`). Les valeurs effectives sont donc celles par défaut : **10 s** pour Docker Compose, **30 s** pour Kubernetes. Aucune option de reprise n’est activée (`acks_late`, `reject_on_worker_lost`).

| Essai | Ce qui est simulé | Action | Réaction de Celery | Statut du document après relance | File / non acquittés | Reprise, signalement |
|---|---|---|---|---|---|---|
| **K1** | perte d’un processus (mémoire, plantage) | `kill -9` du processus enfant qui exécute la tâche ; maître intact | le maître constate la perte (`WorkerLostError`) et remplace l’enfant | **« analyse » indéfiniment** (464 s observées) | 0 / 0 | aucune, aucun |
| **K2** | panne du nœud ou du conteneur | `kill -9` de tout le worker, puis relance | — | **« analyse » indéfiniment** (463 s) | 0 / 0 | aucune, aucun |
| **K3a** | arrêt Compose par défaut (déploiement, redémarrage) | SIGTERM au **seul maître**, puis `kill -9` de tout le worker au bout de 10 s | arrêt « à chaud » amorcé (attente de la tâche), interrompu par le `kill -9` | **« analyse » indéfiniment** (463 s) | 0 / 0 | aucune, aucun |
| **K3b** | arrêt avec une grâce suffisante (informatif) | SIGTERM au **seul maître**, attente jusqu’à 900 s | arrêt « à chaud » : la tâche **se termine** (réussie, 296,6 s), puis le worker sort de lui-même 281 s après le signal | **« analysé »** (5 pages) | 0 / 0 | sans objet |
| K3 initial (**exclu**) | — | SIGTERM à **tous** les processus du worker (erreur de mon outil, D-MES-03) | enfants tués (`WorkerLostError`) | « analyse » indéfiniment | 0 / 0 | aucune, aucun |

**Lecture (MESURÉ-S).**

1. **D-OPS-01 confirmé.** Dans les **quatre** arrêts où la tâche n’a pas pu se terminer (K1, K2, K3a et l’essai initial exclu), le document reste **indéfiniment** au statut « analyse », sans signalement ni reprise. Sa date de mise à jour reste celle de la première seconde. La file Redis est vide et ne contient aucun message non acquitté : la tâche, acquittée dès sa réception, a **disparu**. Rien dans le produit ne la relance ni ne détecte le document orphelin. Le même phénomène a laissé 2 pièces de D9 au statut « traduction » (§5.6).
2. **Un simple déploiement suffit à perdre une tâche.** K3a reproduit l’arrêt par défaut de Compose : 10 s de grâce, alors qu’une page de scan demande 52 à 122 s d’OCR et une traduction plusieurs minutes. Avec Kubernetes (30 s, non testé), le mécanisme est le même pour toute tâche de plus de 30 s (ESTIMÉ, déduit de K3a et K3b). Pendant les mesures, toutes les tâches d’OCR et de traduction ont duré plus de 30 s.
3. **L’arrêt « à chaud » de Celery fonctionne** quand on lui laisse le temps (K3b) : le maître cesse de prendre des tâches, laisse finir celle en cours, puis s’arrête. Pour qu’il protège toutes les tâches, la grâce devrait couvrir la plus longue, soit jusqu’à la limite dure de 1 860 s. Cette mesure ne protège **pas** contre K1 et K2 (plantage, panne), qui exigent une reprise : acquittement en fin de tâche, tâches rejouables sans effet de bord, détection des documents orphelins. Ces corrections relèvent de la Phase C ; leur référence avant correction est ce tableau.
4. **Observation.** Une tâche d’analyse acquittée puis perdue ne laisse aucune trace exploitable par l’exploitant : ni signalement, ni erreur en base. Le seul symptôme est un document dont le statut ne change plus.

## 8. Coût du tokenizer par document (B5)

Les fonctions du produit audité (`_load_local_tokenizer`, `_tokenizer_hash`) sont appelées telles quelles, sans modification, trois fois dans trois processus neufs. Le tokenizer est celui du moteur de mesure ; le tokenizer Qwen de la cible n’a pas été mesuré (**NON MESURÉ**).

| Répétition | Import de la bibliothèque | 1er chargement | 2e chargement, même processus | Empreinte des fichiers |
|---:|---:|---:|---:|---:|
| 1 | 2,34 s | 4,17 s | 3,31 s | 0,099 s |
| 2 | 1,10 s | 3,30 s | 3,67 s | 0,102 s |
| 3 | 1,15 s | 3,20 s | 2,75 s | 0,088 s |

**D-PERF-TOK confirmé (MESURÉ-S).** Un chargement coûte **2,75 à 4,17 s**. Le second chargement dans le même processus n’est pas plus rapide que le premier : **il n’y a aucun cache**. Comme le moteur est recréé pour chaque document (§3.5), ce coût est payé **à chaque document traduit**. Il explique l’essentiel des 3,2 à 3,8 s de préparation des blocs relevés sur le chemin réel (§5.7), et donc la majeure partie de « l’orchestration non détaillée ». Le calcul d’empreinte est, lui, négligeable (environ 0,1 s).

**Portée.** Environ 3 à 4 s par document, soit moins de 1 % d’une traduction de D2 avec le moteur de mesure. Avec un moteur cible rapide, ce coût fixe peut devenir visible sur les petits documents (non mesuré). C’est une optimisation de Phase C, dans un fichier gelé (`service.py`), sans effet sur la fidélité.

## 9. Défauts et constats à la fin de la Phase A

« Nouveau » : établi pendant la Phase A. « Confirmé » : défaut du LOT 2.2 remesuré sur le chemin réel. « Reconduit » : non remesuré, statut inchangé. « Gelé » : le correctif touche un fichier de la liste des composants gelés et exige votre accord explicite.

| ID | Gravité | Constat | Preuve (Phase A) | Statut | Gelé | Phase proposée |
|---|---|---|---|---|---|---|
| **D-DET-02** | **Critique** | blocs étrangers étiquetés « français » **ni traduits ni signalés** (perte silencieuse) | MESURÉ-S chemin réel : 15,5 à 16,7 % des blocs des PDF natifs étiquetés français ; D2 : 23 blocs jamais envoyés au moteur, **1 seul** signalement « non traduit » (au LOT 2.2, 13 de ces 23 blocs étaient du texte anglais) | confirmé | oui | **B, priorité 1** |
| **D-ENG-01** | **Critique** (fonctionnel) | délai moteur fixé à 60 s dans le code, **non configurable**, incompatible avec le budget de sortie de 8 000 jetons | LU `service.py:1039`, `jobs.py` ; MESURÉ-S : 6 appels sur 9 échoués en régime strict (§5.1). Échec **visible** (signalé), pas silencieux | **nouveau** | non : `jobs.py` (non gelé) peut transmettre le délai, que `service.py` lit déjà dans les options | **B, priorité 2** (valeur à décider, §12) |
| **D-REC-02** | **Critique** | chemin Surya : colonne de tableau scanné fusionnée, texte traduit absent du PDF final | REPRIS (LOT 2.2), non remesuré ; D1/D2 relèvent 8 et 26 signalements de réduction de police et 1 régression de géométrie, à qualifier | reconduit | non | B |
| **D-OPS-02** | **Critique** | délai de tâche de 1 800 s incompatible avec les tailles acceptées (200 pages) ; à l’échec, **tout** le travail de la tâche est perdu | MESURÉ-S chemin réel, D9 : **4 traductions de 1 page tuées à 1 800 s** (deux processus pour un moteur à une file), statut échec, 1 seul signalement. ESTIMÉ : analyse d’un scan ≈ 28 pages au plus (63,2 s/page, D4) ; 15 à 23 pages sur les scans denses (77 à 119 s/page, D7) ; traduction ≈ 13 pages (137,9 s/page, D2) | **confirmé (chemin réel)** | non | C |
| **D-REC-01** | Élevée | aucun golden sur le chemin Surya (les 8 golden forcent Tesseract) | MESURÉ (livrable 9, §4) | reconduit | non | B |
| **F-L2-03** | Élevée | glossaire client perdu à cause de la ponctuation collée | test `xfail` toujours en échec attendu (livrable 9, §3) | reconduit | oui | B |
| **F-L2-02** | Élevée | rognage du prompt inopérant ; glossaire rogné avant les décisions | REPRIS | reconduit | oui | B |
| **D-SUP-01** | Élevée | CI rouge : Pillow 12.3.0 (39 avis, correctif en version **majeure** 13.0.0) ; 27 vulnérabilités `npm` (6 élevées, outillage) | MESURÉ (livrable 9, §5–6) ; antérieur au LOT 2.3 | **nouveau** (dans ce suivi) | non | B (Pillow avec golden rejoué et pixels qualifiés) |
| **D-OPS-01** | Élevée | acquittement à la réception, aucune reprise, aucune grâce d’arrêt configurée : tâche perdue si le worker s’arrête, document figé sans alerte | LU (Celery, Compose, Helm) ; MESURÉ-S B4 (§7) : **4 arrêts sur 4** sans grâce suffisante laissent le document **indéfiniment** au statut « analyse », file vide, sans signalement ni reprise, **y compris l’arrêt par défaut de Compose** (K3a, 10 s) ; seule une grâce couvrant la tâche (K3b) la laisse finir ; D9 : 2 pièces figées au statut « traduction » | **confirmé** | non | C (grâce d’arrêt documentée dès que possible ; reprise et détection des orphelins) |
| **D-ENG-04** | Élevée | génération emballée jusqu’au plafond fixe de 8 000 jetons ; avec un moteur à une file, elle bloque tous les documents | MESURÉ-S D9 : 7 705 jetons en 1 293 s ; l’autre processus attend 1 315 s ; 1 requête sur 119. Cause non établie | **nouveau** | non | C (plafond de sortie proportionnel à l’entrée ; à intégrer dans la décision D-ENG-01) |
| **D-REC-03** | Élevée | tableaux des PDF **natifs** : cellules traduites absentes du rendu (signalées) | MESURÉ-S D9 : `PDF_TABLE_CELL_TARGET_MISSING` 214 signalements critiques sur 5 pièces de 1 page | **nouveau** | non | B (qualification visuelle avant correction) |
| **D-OCR-02** | Élevée | Surya sert une page à la fois : un second worker n’apporte quasiment rien sur les scans | MESURÉ-S D6 : gain 4,1 % ; second document +115 % | confirmé | non | C |
| **D-OCR-06** | Élevée | `OMP_THREAD_LIMIT=1` hérité ralentit Surya en silence | MESURÉ-S B2, vrai point d’entrée : **×3,27** (×3,25 à ×3,29) sur 3 pages, toutes en HTTP 200, aucun message ni signalement (§6.2) | confirmé | non (`entrypoint.sh`) | C (correctif court) |
| **D-OCR-07** | Moyenne | le texte lu par Surya **dépend du nombre de fils** (stable à configuration fixe) | MESURÉ-S B1 : page arabe F1 0,8219 avec 5 fils, 0,8299 avec 4 ; 5 autres pages identiques (§6.1) | **nouveau** | non | B (le golden Surya de D-REC-01 doit fixer fils et quantification) |
| **D-PERF-TOK** (lié à D-MET-03) | Moyenne | tokenizer rechargé depuis le disque à **chaque** document | LU `service.py:352`, `:942` ; MESURÉ-S chemin réel : temps propre de `traduction.blocs` 3,4 à 5,8 s par document ; MESURÉ-S B5 : **2,75 à 4,17 s par chargement, second chargement aussi lent que le premier (aucun cache)** (§8) | **nouveau**, confirmé | oui (`service.py`) | C |
| **D-OBS-01** | Observation | signalements OCR **identiques** pour un scan propre et un fax basse résolution ; l’orientation n’est jamais vérifiée | MESURÉ-S D7 | **nouveau** | non | B (rapport qualité OCR) |
| **D-CLS-01** | Observation | avis de pension classé « facture », sans signalement | MESURÉ-P D8, un seul exemple | **nouveau** | non | B (à confirmer sur le corpus) |
| **D-MES-01** | Méthode | réutilisation de calcul par llama.cpp dans Surya : une image identique servie juste après elle-même est lue 3,5 fois plus vite ; avec le cache de prompts par défaut, toute page relue est 1,4 à 3,3 fois plus rapide | MESURÉ-S S3/D3 : 58,7 s puis 16,8 s ; B1 (§6.1). La configuration du produit (cache désactivé) n’est touchée que par le premier cas | **nouveau** | — | protocole de mesure : première lecture seule, ou cache désactivé et pages différentes |
| **D-MES-02** | Méthode (mon outil) | mon pilote ne renouvelait pas le jeton de session (60 min) ; statuts D9 relus en base | MESURÉ (§5.6) | corrigé dans l’analyse | — | pilote à corriger avant les campagnes suivantes |
| **D-MES-03** | Méthode (mon outil) | (1) mon script visait un mauvais port PostgreSQL : tests PostgreSQL et banc BM25 jamais démarrés à la première exécution ; (2) mon premier essai d’arrêt « SIGTERM » frappait tous les processus du worker, pas le seul maître comme un orchestrateur | MESURÉ (§6.4, §7 ; livrable 9, §7) | corrigé ; mesures rejouées ; premier essai K3 **exclu** | — | — |
| **D-TEL-01** | Faible | libellé de télémétrie `blocks_translated_or_preserved` ambigu (compte aussi les blocs non traduits) | LU `service.py:1774` | **nouveau** | oui | documentation |

Les autres défauts du LOT 2.2 (D-OPS-03, D-OCR-03, D-ENG-02, D-ARB-01, D-DET-03, D-GOV-01, D-PERF-O2, D-PERF-Q, D-MET-01, D-MET-02, D-OCR-04, D-OCR-05, D-LNG-01, D-SEC-01, D-ENG-03, D-BM25-01) sont **reconduits** sans changement de statut.

**Critères GO technique de la consigne non satisfaits à ce jour** : perte silencieuse de blocs (D-DET-02) ; reprise des tâches (D-OPS-01) ; non-régression sur le chemin par défaut (D-REC-01) ; performance sur l’infrastructure cible (moteur cible jamais exécuté).

## 10. Risques

| Risque | Probabilité | Impact | Maîtrise proposée |
|---|---|---|---|
| Le moteur cible ne tient pas 133 jetons/s par requête : D-ENG-01 rend la traduction incomplète en production | inconnue (**NON MESURÉ**) | traduction incomplète sur chaque document long ; revue humaine surchargée | mesurer le moteur cible dès qu’il est accessible ; rendre le délai configurable (Phase B) |
| Relever le délai moteur sans plafonner la sortie (D-ENG-01 sans D-ENG-04) | moyenne | une génération emballée bloque le moteur pendant des dizaines de minutes ; les tâches voisines dépassent 1 800 s et perdent tout leur travail | traiter D-ENG-01 et D-ENG-04 ensemble ; plafond de sortie lié à l’entrée |
| Documents figés au statut « analyse » ou « traduction » après un arrêt de worker | **élevée** : chaque déploiement avec la grâce par défaut, chaque incident (MESURÉ-S, §7) | dossier client figé sans alerte | reprise et détection des documents orphelins (Phase C) ; en attendant, procédure d’arrêt documentée : vidage du worker et grâce couvrant la tâche la plus longue |
| Corrections de fidélité dans des fichiers gelés : régression des contrats historiques | moyenne | régression silencieuse | tests de caractérisation avant correction ; golden rejoué ; règle d’empreinte versionnée et documentée |
| Passage à Pillow 13 : pixels du golden modifiés | moyenne | faux échecs ou vraie régression de rendu | golden rejoué, différences qualifiées une à une, pas d’exception d’audit |
| Chiffres du moteur de mesure pris pour ceux de la production | moyenne | plan de capacité faux | étiquetage systématique ; aucun plan de capacité sans le moteur cible |
| Aucun document client réel rempli | certaine à court terme | qualification métier impossible | démarches de l’annexe A1 (partenariat, conventions, autorité de protection des données) |
| Licence des poids Surya non validée | ouverte | blocage de production | décision juridique écrite |

## 11. Proposition pour la Phase B (corrections de fidélité)

La consigne fixe l’ordre suivant : F-L2-03, F-L2-02, D-DET-02, valeurs financières OCR, D-REC-01, D-REC-02. **Je propose un écart, soumis à votre décision (§12)** : traiter d’abord ce qui viole un critère GO (la perte silencieuse D-DET-02), puis D-ENG-01, sans lequel aucune mesure de traduction de la Phase B ne serait complète avec le délai livré. Viennent ensuite les corrections courtes et réversibles. Si vous préférez l’ordre de la consigne, il sera appliqué tel quel. Chaque correction fait l’objet d’un test qui échoue **avant** et réussit **après**, d’un commit séparé au nom de Hamza NORDINE, d’une PR brouillon, sans fusion.

1. **D-DET-02** : un bloc non envoyé au moteur parce qu’il est étiqueté « français » doit être soit **vérifié**, soit **signalé**. Jamais retiré en silence. Fichiers : `jobs.py` (non gelé) et `block_status.py` (gelé).
2. **D-ENG-01** : délai moteur lu dans les réglages et transmis par `jobs.py`, sans toucher au fichier gelé `service.py`, avec un test. La **valeur par défaut** est une décision (§12).
3. **F-L2-03** puis **F-L2-02** : le test `xfail` existant doit devenir un test réussi. Fichier gelé (`builder.py`).
4. **Valeurs financières OCR** : séparateur décimal et montants altérés, mesurés sur l’échantillon OCR du corpus au lot précédent (REPRIS). Test dédié sur les vérités terrain.
5. **D-REC-01** : golden synthétique sur le chemin Surya, avec tableau, **avant** de toucher à la reconstruction ; puis **D-REC-02**.
6. **D-SUP-01** : Pillow 13 avec golden rejoué et différences de pixels qualifiées.

Les points de performance (D-OPS-01, D-OPS-02, D-OCR-02, D-OCR-06, D-PERF-TOK) relèvent de la Phase C. Leur référence avant correction figure dans ce rapport.

## 12. Décisions demandées

1. **Valider le diagnostic de la Phase A** et autoriser la Phase B, **dans l’ordre proposé au §11 ou dans celui de la consigne**. Aucune ligne de code produit ne sera modifiée avant votre accord.
2. **Autoriser la modification des fichiers gelés** nécessaires à D-DET-02 (`block_status.py`), F-L2-03 et F-L2-02 (`builder.py`), avec une empreinte de référence versionnée et documentée.
3. **D-ENG-01, valeur du délai moteur.** (a) réglable, défaut 60 s inchangé ; (b) réglable, défaut aligné sur le budget de sortie ; (c) appel en flux avec délai d’inactivité. Le choix dépend du moteur cible : **quel moteur et quel débit en production ?** À décider avec un plafond de sortie proportionnel à l’entrée (D-ENG-04) : relever le délai sans ce plafond exposerait tout le service à une génération emballée (§10).
4. **Accès au moteur cible** (service privé et tokenizer Qwen), pour le mesurer. Sans lui, le plan de capacité restera **NON MESURÉ**.
5. **D-OPS-01, mesure d’exploitation.** La reprise des tâches relève de la Phase C. Mais fixer dès maintenant une grâce d’arrêt couvrant la tâche la plus longue (Compose et Helm) et documenter la procédure d’arrêt réduirait la perte lors des déploiements. Cela modifie des fichiers de déploiement : **à traiter en Phase B, ou à laisser en Phase C ?**
6. Décisions encore ouvertes des lots précédents : **licence des poids Surya** (écrite) et **orientation des pages** (D-OCR-03).

**Production : NO-GO.** Rien dans la Phase A ne lève ce statut.

## 13. Reproduction

Les mesures ont été faites avec des scripts **privés, hors dépôt** : démarrage d’une infrastructure temporaire (PostgreSQL 16, Redis, MinIO) ; lancement de l’API et du worker avec les commandes de Compose ; enveloppes de traces installées au démarrage des processus ; pilote HTTP de l’API ; échantillonneur de ressources ; agrégations. Ils ne contiennent aucune donnée et ne sont pas versionnés, conformément à la règle de confidentialité. Les entrées sont les fichiers du corpus, identifiés par leur nom et vérifiés par empreinte (§4). Les traces ne contiennent **aucun texte** de document.
