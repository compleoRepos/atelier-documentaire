# OCR Surya — guide d’intégration, de déploiement et d’exploitation

> Statut : **intégré, moteur OCR par défaut, NON qualifié pour la production.**
> Un humain reste systématiquement dans la boucle de validation, quel que soit le score.
> Auteur des modifications : Hamza NORDINE.

## 1. Décision et périmètre

Sur instruction du responsable produit, l’OCR des pages scannées n’utilise plus Tesseract mais
**Surya OCR 2.5** (Datalab), exécuté localement sur CPU. Règles appliquées :

| Règle | Mise en œuvre |
|---|---|
| Surya par défaut | `TRANSLATOR_OCR_BACKEND=surya` (valeur par défaut du code, de Compose et de Helm). |
| Tesseract seulement sur sélection explicite | `TRANSLATOR_OCR_BACKEND=tesseract` : référence historique des tests de non-régression et du golden, retour arrière. |
| Aucun repli automatique | Si le service Surya est indisponible, **l’analyse du document échoue** (erreur `OCR_SURYA_UNAVAILABLE`, mesurée) ; le pipeline **ne bascule jamais** silencieusement vers un autre moteur. |
| Aucun appel Tesseract sur le chemin Surya | Orientation OSD, relecture de lignes et récupération F25 ne passent plus par Tesseract quand Surya est le moteur (voir §5). |
| Traitement 100 % local | Aucun appel réseau sortant : poids montés en lecture seule, `HF_HUB_OFFLINE=1`, inférence sur la boucle locale du conteneur. |

Les PDF natifs (texte extractible), DOCX, XLSX et PPTX ne passent pas par l’OCR : la bascule ne les
concerne pas.

## 2. Licence des poids — action humaine obligatoire avant production

- **Code** (`surya-ocr` 0.23.0, client officiel) : Apache 2.0.
- **Poids** (`datalab-to/surya-ocr-2.5`, `datalab-to/surya-ocr-2.5-gguf`) : licence
  « AI Pubs Open RAIL-M **modifiée** ». Extraits lus dans le texte officiel (annexe A) :
  - §2 : usage commercial interdit « for any purpose » si l’entité (ou son employeur / une entité
    affiliée) **(a)** a généré plus de **5 000 000 USD** de chiffre d’affaires brut l’année précédente,
    **(b)** a levé plus de **5 000 000 USD** en capital ou en dette — sauf usage personnel ou de
    recherche — ou **(c)** propose un produit ou service **concurrent** d’un produit ou service du
    concédant (Datalab commercialise une API de conversion, d’OCR et d’analyse de documents) ;
  - §7 attribution, §8 « share-alike » sur les sorties, §4 conditions d’un usage hébergé,
    §9 possibilité de restriction ou de mise à jour à distance par le concédant.
- Au-delà de ces seuils, une **licence commerciale** Datalab est nécessaire
  (<https://www.datalab.to/pricing>).

Conséquence technique (fail-closed) : en environnement `production`, l’application **refuse de
démarrer** avec `TRANSLATOR_OCR_BACKEND=surya` tant que
`TRANSLATOR_SURYA_WEIGHTS_LICENSE_ACKNOWLEDGED=true` n’a pas été positionné par l’exploitant, après
décision juridique documentée. L’évaluation sur données synthétiques relève de l’usage de recherche.
**Cette attestation n’a pas été fournie à ce jour** : la production avec Surya est donc bloquée.

## 3. Architecture

```
worker (Celery)  --HTTP boucle locale ou réseau interne-->  service ocr-surya
   app/ai/ocr/surya_client.py                                 services/ocr-surya/ocr_surya_service.py
   (PNG borné, délai, jeton,                                    (client officiel surya-ocr 0.23.0,
    géométrie de lignes estimée)                                  HTML -> lignes/tableaux, aucun texte journalisé)
                                                                       |
                                                                       |  HTTP 127.0.0.1:8091 (dans le conteneur)
                                                                       v
                                                                llama-server (llama.cpp b11700, CPU)
                                                                surya-2.5-Q8_0.gguf + surya-2.5-mmproj.gguf (lecture seule)
```

| Déploiement | Topologie | URL côté application |
|---|---|---|
| Kubernetes (Helm) | conteneur annexe `ocr-surya` dans le pod **worker** (et dans le pod API si `external.executionMode=inline`), écoute `127.0.0.1:8093` | `http://127.0.0.1:8093` |
| Docker Compose (laboratoire / recette) | service `ocr-surya` sur le réseau interne `private` | `http://ocr-surya:8093` |

En production, le contrat de configuration exige HTTPS dès que l’hôte n’est pas la boucle locale :
la topologie « conteneur annexe » de Helm est donc la seule acceptée telle quelle ; une URL
`http://ocr-surya:8093` est **refusée** en production (fail-closed), ce qui impose un TLS de bout en
bout pour toute autre topologie.

Image `services/ocr-surya/Dockerfile` :
- base `python:3.12-slim-bookworm` ; environnement Python **figé** (`requirements.lock`, 56 paquets,
  `torch` CPU) ;
- `llama-server` issu de l’archive officielle llama.cpp **b11700** (Ubuntu x64 CPU), contrôlée par son
  **SHA-256 publié** lors de la construction ;
- utilisateur non root (UID 10001), système de fichiers en lecture seule, `/tmp` en tmpfs,
  capacités supprimées ;
- cache de prompts de llama.cpp **désactivé** (`--cache-ram 0`, voir §8) : aucun prompt dérivé
  d’une page n’est conservé en mémoire d’une requête à l’autre ;
- **aucun poids dans l’image**.

## 4. Obtenir et vérifier les poids

Fichiers officiels (dépôt `datalab-to/surya-ocr-2.5-gguf`) et empreintes SHA-256 contrôlées par
l’entrypoint à **chaque** démarrage (aucun contournement possible) :

| Fichier | Taille (octets) | SHA-256 |
|---|---:|---|
| `surya-2.5-Q8_0.gguf` (quantifié Q8_0, **défaut**, voir §9) | 628 680 096 | `5ab34c76845f66d2882ec5c89735894b700e0a7decd08898ab962b2afb9aca57` |
| `surya-2.5.gguf` (bf16, option) | 1 180 178 976 | `45fa3e587cf5a475f06e949fbe40e67b759dbcee1830e7effbcb172445d4b6bf` |
| `surya-2.5-mmproj.gguf` (projecteur vision, obligatoire) | 207 345 920 | `f245dbf784cf73683a273a37fefae0d0d7983b083a5d2fecf9309476f861f659` |

Procédure (poste d’administration disposant d’un accès Internet approuvé, **après** validation de
la licence) :

```bash
mkdir -p surya-models && cd surya-models
for f in surya-2.5-Q8_0.gguf surya-2.5-mmproj.gguf LICENSE; do
  curl -fL -o "$f" "https://huggingface.co/datalab-to/surya-ocr-2.5-gguf/resolve/main/$f"
done
cat > SHA256SUMS <<'EOF'
5ab34c76845f66d2882ec5c89735894b700e0a7decd08898ab962b2afb9aca57  surya-2.5-Q8_0.gguf
f245dbf784cf73683a273a37fefae0d0d7983b083a5d2fecf9309476f861f659  surya-2.5-mmproj.gguf
EOF
sha256sum -c SHA256SUMS
```

Pour utiliser le bf16, télécharger aussi `surya-2.5.gguf`, ajouter sa ligne d’empreinte et
positionner `OCR_SURYA_MODEL_FILE=surya-2.5.gguf` (Compose) ou `ocr.surya.modelFile` (Helm).

Transférer ensuite le répertoire vers le volume `surya-models` (Compose) ou le PVC
`ocr.surya.modelClaim` (Helm), monté **en lecture seule**. Un fichier absent, non référencé ou dont
l’empreinte diffère provoque un arrêt immédiat du conteneur (code 78) sans exposer de service.

## 5. Effets sur le pipeline documentaire

| Étape | Avec Tesseract (référence) | Avec Surya |
|---|---|---|
| Lecture d’une page scannée | jusqu’à 6 variantes de prétraitement, chacune relue | **une seule lecture** (variante retenue par le prétraitement géométrique) ; réglable par l’option `surya_preprocessing_max_variants` |
| Orientation 90°/180°/270° | OSD Tesseract | **non corrigée** (Surya n’a pas de fonction d’orientation documentée) ; le redressement fin (deskew, OpenCV) reste actif. Mesure S2 (§9) : **forte perte en arabe** sur page tournée, peu d’effet en anglais et en français |
| Géométrie | boîtes mots/lignes natives | blocs natifs Surya ; **lignes estimées** par projection d’encre dans chaque bloc (signalées comme estimées) |
| Double lecture des entités critiques | Tesseract `psm 7` | Surya en mode bloc (`/v1/ocr/block`) ; une relecture tronquée est traitée comme **non concluante** |
| Récupération F25 des lignes peu sûres | relecture Tesseract | **désactivée** (non calibrée pour Surya) ; chaque bloc concerné est compté (`ocr_recovery_disabled_blocks`), jamais silencieux |
| Provenance | `ocr:tesseract` | `ocr:surya`, avec la version du moteur et le libellé du modèle effectivement chargé (`surya-ocr-2.5:surya-2.5-Q8_0` ou `surya-ocr-2.5:surya-2.5`), fixé par l’entrypoint après contrôle d’empreinte |

## 6. Configuration

Application (API et worker) :

| Variable | Défaut | Rôle |
|---|---|---|
| `TRANSLATOR_OCR_BACKEND` | `surya` | `surya` ou `tesseract` (sélection explicite, aucun repli) |
| `TRANSLATOR_SURYA_OCR_URL` | — (requis en production) | URL du service OCR |
| `TRANSLATOR_SURYA_OCR_ALLOWED_HOSTS` | `127.0.0.1,localhost,::1` | hôtes autorisés ; tout autre hôte est refusé au démarrage |
| `TRANSLATOR_SURYA_OCR_TOKEN` | — | jeton porteur facultatif (recommandé hors boucle locale) |
| `TRANSLATOR_SURYA_OCR_TIMEOUT_SECONDS` | `900` | délai maximal par requête OCR (10–3600) |
| `TRANSLATOR_SURYA_WEIGHTS_LICENSE_ACKNOWLEDGED` | `false` | attestation d’éligibilité à la licence des poids (obligatoire en production) |

Service `ocr-surya` :

| Variable | Défaut | Rôle |
|---|---|---|
| `OCR_SURYA_MODEL_FILE` | `surya-2.5-Q8_0.gguf` | `surya-2.5.gguf` (bf16) possible ; tout autre fichier est refusé (code 78) |
| `OCR_SURYA_THREADS` | `4` | threads d’inférence |
| `OCR_SURYA_PARALLEL` | `1` | requêtes simultanées du moteur (contexte = 12 288 jetons par requête) |
| `OCR_SURYA_TOKEN` | — | jeton exigé sur `/v1/ocr/*` s’il est défini |
| `OCR_SURYA_MAX_INFLIGHT` | `1` | requêtes OCR traitées simultanément par le service |
| `OCR_SURYA_MAX_BODY_BYTES` / `OCR_SURYA_MAX_PIXELS` | 40 Mio / 40 Mpx | bornes des images reçues (PNG uniquement) |
| `OCR_SURYA_BIND` | `127.0.0.1` (Helm), `0.0.0.0` (image, réseau interne Compose) | une écoute hors boucle locale exige `OCR_SURYA_ALLOW_NON_LOOPBACK=1` |

`/health` est accessible sans jeton (sondes Docker/Kubernetes) et ne renvoie qu’un état et des
versions ; les routes OCR exigent le jeton s’il est configuré.

## 7. Docker Compose (laboratoire / recette)

1. Renseigner `.env` à partir de `.env.example` (section OCR) ; générer `OCR_SURYA_TOKEN`.
2. Peupler le volume des poids (une fois) :
   ```bash
   docker volume create atelier-documentaire_surya-models
   docker run --rm -v atelier-documentaire_surya-models:/models -v "$PWD/surya-models:/src:ro" \
     busybox sh -c 'cp /src/surya-2.5-Q8_0.gguf /src/surya-2.5-mmproj.gguf /src/LICENSE /models/'
   ```
   (le nom exact du volume dépend du nom de projet Compose : vérifier avec `docker volume ls`).
3. `docker compose --env-file .env config --quiet`, puis `docker compose build ocr-surya`.
4. `docker compose up -d ocr-surya` ; attendre `healthy` (démarrage : contrôle des empreintes puis
   chargement du modèle, jusqu’à 10 minutes autorisées).
5. Démarrer l’API et le worker : le worker dépend de `ocr-surya` en état `healthy`.

## 8. Kubernetes (Helm)

Valeurs `ocr.*` du chart :

```yaml
ocr:
  backend: surya              # tesseract = retour arrière explicite
  surya:
    image: <registre>/atelier-documentaire-ocr-surya
    tag: "<version construite>"
    modelClaim: atelier-documentaire-surya-models   # PVC des poids, monté en lecture seule
    modelFile: surya-2.5-Q8_0.gguf                  # ou surya-2.5.gguf (bf16)
    threads: 4
    timeoutSeconds: 900
    weightsLicenseAcknowledged: false               # true seulement après décision juridique
    resources:
      requests: { cpu: "2", memory: 5Gi }
      limits: { cpu: "4", memory: 6Gi }
```

Le conteneur annexe a des sondes `startup`/`readiness`/`liveness` de type `exec` sur la boucle
locale, un système de fichiers en lecture seule et `/tmp` en `emptyDir`. Avec `ocr.backend=tesseract`,
aucun conteneur annexe ni volume de poids n’est rendu. Contrôle :

```bash
helm lint infrastructure/helm/atelier-documentaire
helm template ci infrastructure/helm/atelier-documentaire > rendu.yaml
helm template ci infrastructure/helm/atelier-documentaire --set ocr.backend=tesseract > rendu-tesseract.yaml
```

Dimensionnement mémoire. Le pic (VmHWM) a été mesuré sur le service réel et sur pages synthétiques
de 2 Mpx environ, rastérisées à 144 dpi :

| Configuration | llama-server | Service HTTP | Total |
|---|---:|---:|---:|
| Q8_0, cache de prompts désactivé (configuration livrée, 6 pages) | 1,48 Gio | 0,29 Gio | ≈ 1,8 Gio |
| bf16, 2 pages | 1,99 Gio | 0,29 Gio | ≈ 2,3 Gio |

Le cache de prompts de llama.cpp, actif par défaut jusqu’à 8 192 Mio dans b11700, faisait croître
le pic d’environ 85 Mio par page (A/B sur 6 pages Q8_0 : de 1,37 à 1,79 Gio, contre un plafond de
1,48 Gio sans cache). Le bf16 atteignait ainsi 4,0 Go après 72 pages. Un service de longue durée
aurait fini par dépasser la limite de 6 Gio. L’entrypoint le désactive (`--cache-ram 0`), à F1
identique sur les 6 pages et sans ralentissement mesuré (48,2 s contre 50,4 s par page). La requête
et la limite ci-dessus (5 Gio et 6 Gio) sont conservées par prudence : aucune mesure n’a été faite
sur de grandes images (la borne est de 40 Mpx) ni en charge. Elles s’ajoutent à celles du worker.
L’entrypoint a été exécuté de bout en bout hors conteneur, avec les vrais poids Q8_0 : contrôle
d’empreinte et chargement en 6 s, une page lue, arrêt propre sur SIGTERM.

Validation de l’image. La CI prévoit la construction de l’image, son autotest hors réseau et son
refus de démarrer sans poids (job `container-and-manifest-validation`). Ce job est aujourd’hui
**sauté** : il dépend des jobs `backend` et `frontend`, qui échouent sur des audits pip et npm
antérieurs à cette branche et traités séparément. Ces contrôles ont donc été rejoués **localement**
sur l’image construite depuis cette branche (0,47 Go, UID 10001) :

- refus de démarrer sans poids (code 78) et autotest hors réseau ;
- exécution de bout en bout sans réseau, système de fichiers en lecture seule, sans capacités, poids
  montés en lecture seule : service sain en 12 s, une page lue avec la provenance
  `surya-ocr-2.5:surya-2.5-Q8_0`, aucune connexion sortante possible, 1,63 Gio.

Arrêt du service. Après avoir servi une requête, llama-server ne se termine pas toujours sur
SIGTERM : il est resté vivant 20 s dans un essai, jusqu’au SIGKILL de Docker (code 137). L’entrypoint
borne donc l’arrêt : SIGTERM aux deux processus, puis SIGKILL de ce qui survit après 5 s. C’est sans
perte, car le moteur ne garde aucun état persistant. Vérifié : arrêt en 0,2 s après une lecture
(code 143), et en 5,1 s face à un moteur factice qui ignore SIGTERM, sans processus survivant.

## 9. Mesures (synthétiques uniquement)

Aucun document réel n’a été envoyé à Surya. Les protocoles et leurs règles de décision ont été
fixés **avant** la lecture des résultats.

Conditions : machine de 6 vCPU x86-64 sans GPU ; llama.cpp b11700 ; 5 threads d’inférence sur
5 cœurs dédiés, client sur le sixième ; pages rastérisées à 144 dpi (chemin du produit).
Corpus : 72 pages synthétiques générées par le projet, soit 60 cas : 57 langues ou écritures à
raison d’une page chacune, plus l’anglais en qualités propre, moyenne et dégradée (5 pages
chacune). Métrique : F1 « sac de mots » (ordre ignoré) contre le texte source de la page. Ce
n’est ni un CER ni une validation humaine. Tesseract est mesuré sur les mêmes images, en
mono-thread, dans deux configurations : celle du produit (7 modèles
`ara+deu+eng+fra+ita+nld+spa`) et la meilleure configuration mesurée pour chaque cas, choix
volontairement favorable à Tesseract. Un écart compte s’il dépasse 0,02 en valeur absolue.

### 9.1 Précision (S1, poids bf16, 72 pages, 0 erreur)

| Comparaison sur 60 cas | Surya meilleur | Équivalent | Surya moins bon |
|---|---:|---:|---|
| contre Tesseract, configuration du produit | 38 | 20 | 2 : arabe (−0,030), tifinagh (−0,040) |
| contre la meilleure configuration Tesseract | 12 | 44 | 4 : arabe, darija en écriture arabe, turc, tifinagh |

Le F1 moyen sur les 60 cas est de 0,940 pour Surya, de 0,784 pour Tesseract dans la
configuration du produit et de 0,919 pour sa meilleure configuration. L’essentiel de l’avantage
de Surya vient des écritures que les 7 modèles Tesseract du produit ne couvrent pas (cyrillique,
grec, hébreu, chinois, japonais, coréen, thaï) et de la page anglaise dégradée. Sur les 17 cas où
Tesseract du produit atteint déjà 0,95, l’écart est faible (0,996 contre 0,989).

| Langues du produit | Surya | Tesseract (produit) | Tesseract (meilleure config.) |
|---|---:|---:|---:|
| Français | 0,983 | 1,000 | 1,000 |
| **Arabe** | **0,822** | **0,851** | 0,851 |
| Arabe, chiffres arabes orientaux | 0,853 | 0,813 | 0,827 |
| Darija (écriture arabe) | 0,936 | 0,930 | 0,958 |
| Anglais propre (5 pages) | 1,000 | 0,996 | 0,996 |
| Anglais moyen (5 pages) | 1,000 | 0,994 | 1,000 |
| Anglais dégradé (5 pages) | 1,000 | 0,615 | 0,654 |
| Espagnol | 1,000 | 0,975 | 0,988 |
| Allemand | 1,000 | 0,981 | 0,987 |

Pour un flux arabe vers français, la bascule n’apporte donc **pas** de gain mesuré sur l’arabe :
elle le dégrade légèrement sur cette page. Sept cas restent sous 0,80 avec Surya : hindi (0,587),
tifinagh (0,587), bengali (0,667), amharique (0,673), ourdou (0,714), yoruba (0,770) et igbo (0,787).

**La confiance renvoyée par Surya n’est pas calibrée.** Sa moyenne est de 0,984 sur les 72 pages,
et elle reste à 0,991 sur la page hindi lue à F1 0,587, à 0,990 en bengali (F1 0,667) et à 0,987 en
arabe (F1 0,822). La corrélation entre confiance et F1 n’est que de 0,45. L’avertissement
`OCR_LOW_CONFIDENCE` (confiance < 0,70) ne se déclenche donc presque jamais : son absence ne
signifie pas que la lecture est correcte, et la revue humaine reste obligatoire.

### 9.2 Q8_0 contre bf16 (règle fixée avant mesure)

Règle : Q8_0 n’est adopté que si l’écart de F1 avec le bf16 est au plus de 0,01 sur **chacune** des
12 pages prioritaires (anglais propre/moyen/dégradé, français, arabe, persan, hébreu, ourdou,
allemand, espagnol, russe, chinois simplifié) **et** si Q8_0 est plus rapide.

Résultat : les F1 sont identiques au dix-millième sur les 12 pages, et Q8_0 met 583,0 s contre
647,8 s, soit 10,0 % de moins (48,6 s contre 54,0 s par page en moyenne). **Q8_0 devient le
défaut.** Le bf16 reste sélectionnable. Cette équivalence ne porte que sur ces 12 pages
synthétiques. Les temps bf16 ont été mesurés pendant que d’autres tests tournaient sur la machine,
mais l’écart concorde avec une mesure dos à dos préalable (43,3 s contre 51,2 s sur une page).

### 9.3 Vitesse et capacité

| Mesure | Surya Q8_0 | Surya bf16 | Tesseract (produit) |
|---|---:|---:|---:|
| Temps écoulé par page, 12 pages prioritaires (moyenne) | 48,6 s | 54,0 s | — |
| Temps écoulé par page, 72 pages (médiane) | — | 53,3 s | 2,6 s (médiane par cas, mono-thread) |
| Par le service réel (HTTP, 2 pages) | 51,1 et 51,4 s | 55,7 et 58,7 s | — |

En temps écoulé, Surya bf16 est environ **21 fois plus lent** que Tesseract (médiane par cas ;
de 7 à 32 fois selon la page), avec 5 cœurs contre 1. En temps CPU, l’écart est d’environ 107 fois
(de 37 à 160 fois), en borne haute qui compte les 5 threads comme pleinement occupés. Q8_0 retire
environ 10 %. L’image règle 4 threads par défaut (`OCR_SURYA_THREADS`), moins que les 5 threads
mesurés : prévoir des pages un peu plus lentes.

Conséquence opérationnelle (estimation, non mesurée de bout en bout) : en mode `celery`, toute
l’analyse d’un document tient dans une seule tâche, bornée par `TRANSLATOR_JOB_SOFT_TIMEOUT_SECONDS`
(1 800 s par défaut). À environ 50 s par page et un conteneur OCR par worker, un scan d’environ
35 pages atteint cette limite, et l’analyse échoue alors au lieu de se terminer. Un scan de
200 pages demanderait près de 3 heures. Pour les gros scans, il faut relever les délais de tâche et
dimensionner le nombre de conteneurs OCR ; aucune mesure de charge n’a été faite.

### 9.4 Orientation (S2, bf16, règle fixée avant mesure)

Trois pages (anglais propre, français, arabe) ont été tournées de 90°, 180° et 270°, puis
comparées au témoin à 0° du même passage. La règle déclare une limitation si le F1 d’une page
tournée perd plus de 0,05.

| Page | 0° | 90° | 180° | 270° |
|---|---:|---:|---:|---:|
| Anglais propre | 1,000 | 1,000 | 0,988 | 1,000 |
| Français | 0,983 | 0,971 | 0,948 | 0,983 |
| **Arabe** | 0,822 | **0,542** | **0,483** | **0,746** |

**Limitation confirmée pour l’arabe**, sur les trois angles (de −0,076 à −0,339). L’anglais et le
français restent dans la tolérance (au pire −0,035). Aggravant : sur la page arabe à 90° et à 270°,
la confiance déclarée reste à 0,97, donc aucun avertissement n’est émis. Seule la page à 180°
(confiance 0,43) en déclencherait un. Le choix d’une correction d’orientation est une décision
ouverte (§12).

## 10. Retour arrière vers Tesseract

Aucune migration de données n’est nécessaire (les IR existantes ne sont pas modifiées) :

- Compose : `TRANSLATOR_OCR_BACKEND=tesseract` dans `.env`, puis `docker compose up -d api worker` ;
  le service `ocr-surya` peut être arrêté.
- Helm : `helm upgrade … --set ocr.backend=tesseract` (le conteneur annexe disparaît du rendu).

Les documents analysés pendant la période Surya gardent leur provenance `ocr:surya` ; une nouvelle
analyse est nécessaire pour obtenir une lecture Tesseract.

## 11. Vérifications après déploiement

1. `GET /health` du service : `{"status": "ok", "engine_version": …}`.
2. Analyse d’un scan **synthétique** : blocs avec provenance `ocr:surya`, aucune erreur
   `OCR_SURYA_*`.
3. Journaux du service : uniquement routes, nombres de pixels/blocs et durées — **aucun texte**.
4. Arrêt volontaire du service : l’analyse d’un scan échoue avec `OCR_SURYA_UNAVAILABLE` (pas de repli).

## 12. Limites et éléments non démontrés

- **Qualification production : non faite.** Aucune mesure sur documents réels, aucune référence
  humaine, et la décision de licence est en attente (§2). Les mesures du §9 portent sur des pages
  synthétiques, avec une seule page par langue hors anglais : elles orientent, elles ne qualifient pas.
- **Arabe.** Sur page droite, Surya lit moins bien l’arabe que Tesseract (F1 0,822 contre 0,851).
  Sur page tournée, la perte est forte (F1 de 0,483 à 0,746). Le banc interne de Datalab va dans le
  même sens : 45,4 % en arabe contre 90,9 % en français (taux de réussite de tests, pas un CER).
  C’est le principal risque pour un flux arabe vers français.
- **Orientation non corrigée — décision ouverte.** Trois options sont possibles, sans choix fait à
  ce jour : (A) utiliser l’OSD Tesseract pour la seule détection d’orientation, sans lecture de
  texte ; (B) développer une heuristique d’orientation sans Tesseract, à mesurer ; (C) assumer la
  limite, avec revue humaine renforcée des scans arabes. L’option A réintroduit Tesseract dans le
  chemin Surya et contredit la consigne actuelle : elle exige une décision explicite.
- **Confiance non calibrée** (§9.1) : l’absence d’avertissement ne garantit rien.
- **Capacité** (§9.3) : environ 50 s par page sur 5 cœurs. Avec les délais de tâche par défaut, un
  scan au-delà d’environ 35 pages échoue en mode `celery`. Aucune mesure de charge n’a été faite.
- **Arrêt d’un worker pendant l’OCR.** La tâche Celery est acquittée dès sa réception (configuration
  existante, inchangée), et aucun mécanisme ne reprend un document interrompu. Un redémarrage ou un
  déploiement du pod worker pendant l’OCR laisse donc le document en cours sans résultat. Ce
  comportement existait déjà avec Tesseract, mais à environ 50 s par page, la fenêtre d’exposition
  est beaucoup plus large. Il faut vider les workers avant tout déploiement, puis relancer les
  documents concernés.
- Lignes estimées et non natives ; récupération F25 désactivée.
- Le golden historique reste exécuté avec Tesseract épinglé : il garantit la non-régression du
  mode Tesseract, il ne mesure pas Surya.
