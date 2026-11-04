# Données RAG UE : terminologie et droit du travail de l’Union européenne

Ce répertoire contient la base de contenu du RAG constituée à partir de sources officielles de l’Union européenne, complétée d’une paire arabe → français. Toutes les lignes sont importées à l’état de **brouillon** : rien n’est utilisé par une traduction tant qu’une version n’a pas été soumise, validée par une autre personne, publiée puis activée (voir `docs/rag/RAG-UE.md`). Le mode RAG par défaut du produit reste `DISABLED`.

## Contenu

| Répertoire | Contenu | Volume | Usage dans le produit |
|---|---|---|---|
| `eurovoc/` | Thésaurus EuroVoc 4.24 : 894 concepts de 18 microthésaurus (emploi et travail, rémunération, protection sociale, banque, finance, comptabilité, fiscalité, assurance, droit civil, sociétés, migration), en 23 paires `xx → fr` | 20 537 lignes, 23 fichiers CSV | Référentiels terminologiques importables (bibliothèque commune) |
| `eurlex/eurlex/` | Textes du droit du travail de l’UE, article par article : 24 directives et le règlement (CE) n° 883/2004, dans toutes les langues disponibles | 25 actes, 571 couples acte-langue, 11 208 articles-langues | Base de contenu ; **non chargée** dans le produit (recherche juridique = LOT 3) |
| `eurlex/definitions/` | Définitions légales de ces actes, alignées point par point vers le français | 1 654 lignes, 22 fichiers CSV | Référentiels terminologiques importables, juridiction `EU` |
| `wikidata/` | Libellés arabes Wikidata des concepts EuroVoc retenus, alignés sur le terme français officiel EuroVoc | 290 lignes, 325 synonymes ; 70 descripteurs en liste de revue | Référentiel terminologique importable `ar → fr` |

Le français est la langue cible de toutes les paires. Les langues sources couvertes sont les 24 langues officielles de l’UE, plus l’arabe. L’irlandais (`ga`) est présent dans EuroVoc, mais absent des définitions : les actes antérieurs à 2014 n’existent pas en irlandais, et aucune définition irlandaise alignable n’a été trouvée dans les actes récents. L’arabe ne couvre que 361 des 839 descripteurs EuroVoc retenus (43 %) : Wikidata ne fournit pas de libellé arabe pour les autres.

## Sources, licences et mentions

**EuroVoc** — Office des publications de l’Union européenne, version 4.24. La licence CC BY 4.0 est déclarée dans les métadonnées officielles du jeu de données (`dcterms:license`) : la copie de ces métadonnées est conservée dans `eurovoc/eurovoc_metadata-4.24.ttl`. Mention à reproduire : « EuroVoc, © Union européenne, Office des publications, CC BY 4.0 ; données modifiées ».

**EUR-Lex / CELLAR** — textes récupérés auprès de l’Office des publications (`publications.europa.eu/resource/celex/<CELEX>`, négociation de langue), contrôlés langue par langue. © Union européenne. La réutilisation est autorisée moyennant mention de la source (décision 2011/833/UE). **Seuls les textes publiés au Journal officiel de l’Union européenne font foi** : ces fichiers sont une aide terminologique, pas une source juridique opposable. Chaque article et chaque définition indique son numéro CELEX et l’adresse EUR-Lex de l’acte.

**Wikidata** — libellés et alias arabes des éléments portant la propriété P5437 (identifiant EuroVoc), obtenus par le service SPARQL public de Wikidata le 2026-11-03 à 23:57 UTC. Licence CC0 1.0 (domaine public) : aucune mention n’est exigée ; la source est néanmoins tracée ligne par ligne. Le terme français de chaque ligne reste le libellé officiel EuroVoc (CC BY 4.0).

**IATE** — aucune donnée IATE n’est incluse. L’export ciblé s’obtient sur le site IATE avec un compte EU Login. L’outil `tools/rag_ue/iate_tbx_to_csv.py` convertit un export fourni par l’exploitant. Aucune aspiration ni contournement de l’application web n’a été fait.

**Données dérivées dans le code.** Deux modules du produit sont générés à partir de ces sources et le déclarent dans leur en-tête : `backend/app/domain/eu_type_lexicons.py` (expressions de type de document issues des libellés EuroVoc, CC BY 4.0, modifiés) et `backend/app/domain/eu_lang_markers.py` (marqueurs de l’irlandais et du maltais issus des textes EUR-Lex de mise au point, générés par `tools/rag_ue/lang_markers_build.py`).

## Modifications apportées aux données d’origine

Pour EuroVoc, les modifications sont les suivantes : sélection de 18 microthésaurus, mise en paires langue source → français, rattachement aux domaines du produit (`HR`, `PAYROLL`, `BANKING`, `FINANCE`, `TAX`, `INSURANCE`, `LEGAL`, `ADMINISTRATION`) et synonymes tronqués à 500 caractères. La juridiction est laissée vide, car un thésaurus n’est pas une règle de droit : l’origine UE figure dans le contexte et la provenance.

Pour EUR-Lex, aucun texte n’a été réécrit : le texte est seulement extrait du HTML officiel et découpé par article. Le format ancien et le format récent (subdivisions ELI) sont tous deux pris en charge. Le HTML est décodé explicitement en UTF-8. Les intitulés d’articles doivent former une séquence stricte ; un intitulé cité dans le corps d’un article reste du texte. La fin du dispositif est repérée par le lieu et la date de signature ou par l’intitulé d’annexe, dans les 24 langues. L’empreinte SHA-256 du HTML d’origine est conservée pour chaque couple acte-langue.

Pour les définitions, une définition n’est retenue que si l’article de définitions porte exactement les mêmes étiquettes de points en langue source et en français. Le terme est reconnu entre guillemets appariés, ou sous la forme « terme : » sans guillemets lorsque la langue n’en utilise pas (suédois, par exemple). Les étiquettes cyrilliques et grecques sont mises en correspondance par rang. Toute numérotation ambiguë entraîne le rejet de l’article. Le domaine retenu est `HR` (droit du travail) et la juridiction `EU`.

Pour l’arabe, les modifications sont les suivantes : jointure sur la propriété P5437 avec les 839 descripteurs EuroVoc retenus, terme cible = libellé français officiel EuroVoc, domaine EuroVoc, alias arabes en synonymes (tronqués à 500 caractères). Quand plusieurs éléments Wikidata portent le même descripteur (6 cas), l’élément principal est celui dont le libellé français est celui d’EuroVoc, sinon le plus ancien ; les libellés des autres deviennent des synonymes. Un libellé ou un synonyme sans écriture arabe, ou dangereux dans un tableur, est écarté (1 libellé, 5 synonymes). Tous ces cas sont comptés dans `wikidata/manifest.json`. **70 descripteurs sont écartés du fichier importable** et placés dans `wikidata/revue-evaluation-automatique.csv` avec le verdict et le motif de l’évaluation automatique décrite ci-dessous : ils attendent une décision humaine.

## Anomalies connues des textes officiels

Sur 571 couples, 568 ont exactement les mêmes numéros d’articles que la version française. Les 3 autres présentent une anomalie dans le texte officiel lui-même. Les versions italienne de la directive 2000/43/CE et espagnole de la directive 2000/78/CE numérotent deux fois un article « 15 », puis passent directement au « 17 ». La version roumaine de la directive 2002/14/CE ne compte que 13 articles. Dans ces trois cas, l’extraction s’arrête à la rupture : la suite est écartée plutôt qu’attribuée à un mauvais article, et l’anomalie est inscrite dans `eurlex/manifest.json`. Le règlement 883/2004 n’est disponible que dans 12 langues sur la source utilisée. La Charte des droits fondamentaux n’a pas pu être récupérée : l’identifiant interrogé a été refusé par la source.

## Contrôles mesurés

Pour les textes, le rapport de longueur de chaque article à la version française a une médiane de 0,918. 90 % des articles se situent entre 0,747 et 1,07. Seuls 20 articles sur 10 129 sortent de l’intervalle [0,6 ; 1,6], et aucun texte n’est vide.

Pour les définitions, le rapport de longueur à la définition française a une médiane de 0,907. Aucun terme cible n’est tronqué. Passées dans l’importeur du produit (simulation), elles donnent 1 474 lignes acceptées, 180 doublons et 0 erreur. Un doublon correspond à un même couple de termes défini par plusieurs actes : seule la première définition est gardée.

EuroVoc, passé dans l’importeur du produit (simulation), donne 20 537 lignes acceptées et 0 erreur. 55 lignes portent un avertissement (53 collisions de synonymes, 3 cibles concurrentes). La paire arabe passe dans l’importeur avec 0 erreur.

## Évaluation automatique de l’exactitude (pas une revue humaine)

Un échantillon stratifié et tiré au sort (graine fixe 20261104) a été soumis à deux modèles de langue utilisés comme évaluateurs, avec un schéma de réponse strict : `correct`, `acceptable` ou `incorrect`, avec un motif. Les deux évaluateurs proviennent du même fournisseur. Seules des données publiques leur ont été envoyées.

| Données | Paires évaluées | 1er évaluateur : non incorrect | 2e évaluateur : non incorrect | Accord des deux | Borne basse Wilson 95 % (paires jugées non incorrectes par les deux) |
|---|---:|---:|---:|---:|---:|
| Définitions EUR-Lex (10 par langue) | 220 | 220 (100 %) | 218 (99,1 %) | 99,1 % | 218/220 = 99,09 % [96,75 %] |
| EuroVoc (15 par langue) | 345 | 335 (97,1 %) | 336 (97,4 %) | 97,4 % | 331/345 = 95,94 % [93,30 %] |
| Arabe Wikidata (toutes les paires) | 360 | 299 (83,1 %) | 290 sur les 299 conservées (97,0 %) | — | 290/299 = 96,99 % [94,38 %] |

Les rejets EuroVoc sont, pour l’essentiel, des équivalences conceptuelles officielles non littérales (par exemple *Risikodeckung* → « risque couvert ») : la donnée officielle n’a pas été modifiée. Les deux rejets EUR-Lex du second évaluateur portent sur des termes extraits mot pour mot du texte officiel, au même article et au même point ; ce sont très probablement des erreurs de l’évaluateur. Pour l’arabe, seules les paires acceptées par les deux évaluateurs sont importables ; le taux d’erreur résiduel de ces 290 paires n’a pas été mesuré de façon indépendante.

Ces contrôles sont automatiques. **Ils ne remplacent pas la relecture humaine** exigée par la validation à quatre yeux avant toute publication.

## Intégrité

Chaque manifeste (`eurovoc/manifest.json`, `eurlex/manifest.json`, `wikidata/manifest.json`) donne l’empreinte SHA-256 et le nombre de lignes de chaque fichier. Les tests `backend/tests/integration/test_lot24_rag_ue_*.py` vérifient ces empreintes, les comptes, les anomalies déclarées, la séparation entre fichier importable et liste de revue, et le passage dans l’importeur.

## Régénération

```bash
# EuroVoc : archive XML officielle téléchargée au préalable
python tools/rag_ue/eurovoc_to_csv.py --zip eurovoc_xml.zip --out data/rag-ue/eurovoc
# EUR-Lex : répertoires de HTML CELLAR compressés (<CELEX>_<langue>.html.gz)
python tools/rag_ue/eurlex_extract.py --html <répertoires> --acts tools/rag_ue/eurlex_acts.json \
    --out data/rag-ue/eurlex
# Arabe : résultats SPARQL Wikidata (libellés et alias P5437) obtenus au préalable
python tools/rag_ue/wikidata_ar_to_csv.py --labels libelles.json --alt alias.json \
    --retrieved-at 2026-11-03T23:57Z --eurovoc data/rag-ue/eurovoc --out data/rag-ue/wikidata \
    --review data/rag-ue/wikidata/revue-evaluation-automatique.csv
# Marqueurs irlandais et maltais du détecteur de langue (textes EUR-Lex de mise au point)
python tools/rag_ue/lang_markers_build.py --eurlex <textes EUR-Lex> --out backend/app/domain/eu_lang_markers.py
# IATE : export TBX obtenu par l'exploitant avec son compte
python tools/rag_ue/iate_tbx_to_csv.py --tbx export.tbx --export-date AAAA-MM-JJ --out <répertoire>
```
