# Données RAG UE : terminologie et droit du travail de l’Union européenne

Ce répertoire contient la base de contenu du RAG constituée à partir de sources officielles de l’Union européenne. Toutes les lignes sont importées à l’état de **brouillon** : rien n’est utilisé par une traduction tant qu’une version n’a pas été soumise, validée par une autre personne, publiée puis activée (voir `docs/rag/RAG-UE.md`). Le mode RAG par défaut du produit reste `DISABLED`.

## Contenu

| Répertoire | Contenu | Volume | Usage dans le produit |
|---|---|---|---|
| `eurovoc/` | Thésaurus EuroVoc 4.24 : 894 concepts de 18 microthésaurus (emploi et travail, rémunération, protection sociale, banque, finance, comptabilité, fiscalité, assurance, droit civil, sociétés, migration), en 23 paires `xx → fr` | 20 537 lignes, 23 fichiers CSV | Référentiels terminologiques importables (bibliothèque commune) |
| `eurlex/eurlex/` | Textes du droit du travail de l’UE, article par article : 24 directives et le règlement (CE) n° 883/2004, dans toutes les langues disponibles | 25 actes, 571 couples acte-langue, 11 208 articles-langues | Base de contenu ; **non chargée** dans le produit (recherche juridique = LOT 3) |
| `eurlex/definitions/` | Définitions légales de ces actes, alignées point par point vers le français | 1 654 lignes, 22 fichiers CSV | Référentiels terminologiques importables, juridiction `EU` |

Le français est la langue cible de toutes les paires. Les langues couvertes sont les 24 langues officielles de l’UE. L’irlandais (`ga`) est présent dans EuroVoc, mais absent des définitions : les actes antérieurs à 2014 n’existent pas en irlandais, et aucune définition irlandaise alignable n’a été trouvée dans les actes récents.

## Sources, licences et mentions

**EuroVoc** — Office des publications de l’Union européenne, version 4.24. La licence CC BY 4.0 est déclarée dans les métadonnées officielles du jeu de données (`dcterms:license`) : la copie de ces métadonnées est conservée dans `eurovoc/eurovoc_metadata-4.24.ttl`. Mention à reproduire : « EuroVoc, © Union européenne, Office des publications, CC BY 4.0 ; données modifiées ».

**EUR-Lex / CELLAR** — textes récupérés auprès de l’Office des publications (`publications.europa.eu/resource/celex/<CELEX>`, négociation de langue), contrôlés langue par langue. © Union européenne. La réutilisation est autorisée moyennant mention de la source (décision 2011/833/UE). **Seuls les textes publiés au Journal officiel de l’Union européenne font foi** : ces fichiers sont une aide terminologique, pas une source juridique opposable. Chaque article et chaque définition indique son numéro CELEX et l’adresse EUR-Lex de l’acte.

**IATE** — aucune donnée IATE n’est incluse. L’export ciblé s’obtient sur le site IATE avec un compte EU Login. L’outil `tools/rag_ue/iate_tbx_to_csv.py` convertit un export fourni par l’exploitant. Aucune aspiration ni contournement de l’application web n’a été fait.

## Modifications apportées aux données d’origine

Pour EuroVoc, les modifications sont les suivantes : sélection de 18 microthésaurus, mise en paires langue source → français, rattachement aux domaines du produit (`HR`, `PAYROLL`, `BANKING`, `FINANCE`, `TAX`, `INSURANCE`, `LEGAL`, `ADMINISTRATION`) et synonymes tronqués à 500 caractères. La juridiction est laissée vide, car un thésaurus n’est pas une règle de droit : l’origine UE figure dans le contexte et la provenance.

Pour EUR-Lex, aucun texte n’a été réécrit : le texte est seulement extrait du HTML officiel et découpé par article. Le format ancien et le format récent (subdivisions ELI) sont tous deux pris en charge. Le HTML est décodé explicitement en UTF-8. Les intitulés d’articles doivent former une séquence stricte ; un intitulé cité dans le corps d’un article reste du texte. La fin du dispositif est repérée par le lieu et la date de signature ou par l’intitulé d’annexe, dans les 24 langues. L’empreinte SHA-256 du HTML d’origine est conservée pour chaque couple acte-langue.

Pour les définitions, une définition n’est retenue que si l’article de définitions porte exactement les mêmes étiquettes de points en langue source et en français. Le terme est reconnu entre guillemets appariés, ou sous la forme « terme : » sans guillemets lorsque la langue n’en utilise pas (suédois, par exemple). Les étiquettes cyrilliques et grecques sont mises en correspondance par rang. Toute numérotation ambiguë entraîne le rejet de l’article. Le domaine retenu est `HR` (droit du travail) et la juridiction `EU`.

## Anomalies connues des textes officiels

Sur 571 couples, 568 ont exactement les mêmes numéros d’articles que la version française. Les 3 autres présentent une anomalie dans le texte officiel lui-même. Les versions italienne de la directive 2000/43/CE et espagnole de la directive 2000/78/CE numérotent deux fois un article « 15 », puis passent directement au « 17 ». La version roumaine de la directive 2002/14/CE ne compte que 13 articles. Dans ces trois cas, l’extraction s’arrête à la rupture : la suite est écartée plutôt qu’attribuée à un mauvais article, et l’anomalie est inscrite dans `eurlex/manifest.json`. Le règlement 883/2004 n’est disponible que dans 12 langues sur la source utilisée. La Charte des droits fondamentaux n’a pas pu être récupérée : l’identifiant interrogé a été refusé par la source.

## Contrôles mesurés

Pour les textes, le rapport de longueur de chaque article à la version française a une médiane de 0,918. 90 % des articles se situent entre 0,747 et 1,07. Seuls 20 articles sur 10 129 sortent de l’intervalle [0,6 ; 1,6], et aucun texte n’est vide.

Pour les définitions, le rapport de longueur à la définition française a une médiane de 0,907. Aucun terme cible n’est tronqué. Passées dans l’importeur du produit (simulation), elles donnent 1 474 lignes acceptées, 180 doublons et 0 erreur. Un doublon correspond à un même couple de termes défini par plusieurs actes : seule la première définition est gardée.

EuroVoc, passé dans l’importeur du produit (simulation), donne 20 537 lignes acceptées et 0 erreur. 55 lignes portent un avertissement (53 collisions de synonymes, 3 cibles concurrentes).

Ces contrôles sont automatiques. **Ils ne remplacent pas la relecture humaine** exigée par la validation à quatre yeux avant toute publication.

## Intégrité

Chaque manifeste (`eurovoc/manifest.json`, `eurlex/manifest.json`) donne l’empreinte SHA-256 et le nombre de lignes de chaque fichier. Les tests `backend/tests/integration/test_lot24_rag_ue_*.py` vérifient ces empreintes, les comptes, les anomalies déclarées et le passage dans l’importeur.

## Régénération

```bash
# EuroVoc : archive XML officielle téléchargée au préalable
python tools/rag_ue/eurovoc_to_csv.py --zip eurovoc_xml.zip --out data/rag-ue/eurovoc
# EUR-Lex : répertoires de HTML CELLAR compressés (<CELEX>_<langue>.html.gz)
python tools/rag_ue/eurlex_extract.py --html <répertoires> --acts tools/rag_ue/eurlex_acts.json \
    --out data/rag-ue/eurlex
# IATE : export TBX obtenu par l'exploitant avec son compte
python tools/rag_ue/iate_tbx_to_csv.py --tbx export.tbx --export-date AAAA-MM-JJ --out <répertoire>
```
