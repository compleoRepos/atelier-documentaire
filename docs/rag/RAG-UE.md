# RAG UE : exploitation de la bibliothèque commune

Ce guide explique comment charger dans le produit la terminologie et les définitions légales de l’Union européenne décrites dans `data/rag-ue/README.md`. Il précise aussi ce que ces données apportent réellement à une traduction.

## Principes

La **bibliothèque commune** regroupe des référentiels sans tenant (`tenant_id` nul), lisibles par tous les tenants et modifiables uniquement par l’outil d’exploitation de la plateforme : `backend/app/rag/common_library_cli.py`. Aucune route d’API ne permet à un tenant d’y écrire.

Les règles ordinaires du RAG s’appliquent sans exception. Un import crée toujours une version **brouillon**. La validation doit être faite par une **personne différente** de celle qui a soumis la version (quatre yeux). Seule une version publiée **et** un référentiel activé sont utilisés par les traductions. Chaque acteur est un utilisateur actif du produit, et chaque étape est tracée par un événement de validation : l’import, avec son empreinte et ses comptes, est enregistré comme événement « import ».

Le mode RAG par défaut reste `DISABLED`. En `SHADOW`, rien n’est injecté. L’injection n’a lieu qu’en mode `ACTIVE`, avec le moteur privé, pour un tenant dont le mode maximal l’autorise.

## Chargement

Toutes les commandes se lancent depuis `backend/`, avec la configuration habituelle de la base. Chaque commande est une transaction (en cas d’erreur, rien n’est écrit) et renvoie un JSON sans contenu terminologique.

```bash
# 1. EuroVoc : un référentiel par paire (« EuroVoc 4.24 de-fr », ...), versions en brouillon
python -m app.rag.common_library_cli import-eurovoc --dir ../data/rag-ue/eurovoc --actor alice

# 2. Définitions EUR-Lex : un référentiel par paire
python -m app.rag.common_library_cli import --name "EUR-Lex définitions de-fr" --languages de,fr \
    --actor alice ../data/rag-ue/eurlex/definitions/eurlex-de-fr.csv

# 3. Arabe (Wikidata aligné sur EuroVoc) : 290 lignes ; la liste de revue n'est PAS importée
python -m app.rag.common_library_cli import --name "Wikidata EuroVoc ar-fr" --languages ar,fr \
    --actor alice ../data/rag-ue/wikidata/wikidata-ar-fr.csv

# 4. Cycle de validation (validation par une autre personne)
python -m app.rag.common_library_cli transition --name "EUR-Lex définitions de-fr" --version 1 \
    --action submit --actor alice
python -m app.rag.common_library_cli transition --name "EUR-Lex définitions de-fr" --version 1 \
    --action validate --actor bob
python -m app.rag.common_library_cli transition --name "EUR-Lex définitions de-fr" --version 1 \
    --action publish --actor alice
python -m app.rag.common_library_cli activate --name "EUR-Lex définitions de-fr" --actor alice

# 5. Textes du droit du travail article par article (25 actes, 571 couples acte-langue, 11 208 articles) :
#    un seul référentiel réglementaire, même cycle (soumission, validation par une autre personne,
#    publication, activation)
python -m app.rag.common_library_cli import-legal --dir ../data/rag-ue/eurlex --actor alice
python -m app.rag.common_library_cli transition --name "EUR-Lex droit du travail UE textes" --version 1 \
    --action submit --actor alice    # puis validate (bob), publish (alice), activate (alice)

# Consultation des articles publiés et actifs (lecture seule, mots entiers, sans effet sur la traduction)
python -m app.rag.common_library_cli legal-search --query "durée maximale hebdomadaire de travail" \
    --language fr --reference 2003/88

# État de la bibliothèque commune (comptes de textes, d'articles, d'actes et de langues inclus)
python -m app.rag.common_library_cli status
```

Le chargeur `tools/rag_ue/charger_dice_ue.py` enchaîne toutes ces étapes ; l’option `--sans-textes-juridiques` exclut les textes.

Un référentiel est créé par paire de langues, car l’API limite à 20 le nombre de langues déclarées par référentiel. Ce plafond est inférieur aux 25 langues désormais acceptées ; il n’a pas été modifié, pour préserver le contrat de l’API.

## Prérequis : la langue du document doit être reconnue

Le RAG ne cherche un terme que dans les langues sources reconnues dans le document. Jusqu’au LOT 2.3, le produit ne reconnaissait que 7 langues (anglais, français, allemand, italien, espagnol, néerlandais, arabe) : un document grec, polonais ou maltais était classé « langue inconnue », et **aucun terme ne pouvait lui être injecté**, quel que soit le contenu de la bibliothèque. Le détecteur reconnaît désormais les 24 langues officielles de l’UE et l’arabe. Les 7 langues historiques gardent exactement la même décision qu’avant : 2 229 paragraphes de contrôle et 646 documents du corpus bancaire donnent un résultat identique à l’ancien détecteur. Une langue ajoutée n’est retenue que sur preuve forte ; à défaut, le bloc reste « inconnu », comme avant.

Mesure sur des articles EUR-Lex jamais utilisés pour la mise au point (4 320 paragraphes dans les 18 langues ajoutées) : 95,1 % de langues justes, 1,4 % de langues fausses, le reste « inconnu ». Les paragraphes longs (200 à 600 caractères) sont reconnus à 100 %, les moyens (60 à 200) à 98,9 %, les fragments courts (20 à 60 : titres, cellules de tableau) à 86,4 % seulement : c’est la principale limite. La langue du document, calculée sur l’ensemble de son texte, relève du cas des paragraphes longs. Le parcours complet (envoi d’un DOCX, analyse, langue, domaine, recherche, injection dans la consigne du moteur privé simulé) est testé pour chacune des 24 langues sources.

## Ce que ces données apportent, et ce qu’elles n’apportent pas

Les deux types de données n’ont pas la même portée.

**EuroVoc** (domaines `HR`, `PAYROLL`, `BANKING`, `FINANCE`, `TAX`, `INSURANCE`, `LEGAL`, `ADMINISTRATION`, sans juridiction) fournit l’équivalent français institutionnel d’un terme reconnu dans le document source. Ce terme est injecté dans la consigne du moteur pour les documents d’un domaine compatible.

**Les définitions EUR-Lex** (domaine `HR`, juridiction `EU`) fournissent le terme français employé par la version française de la directive. Elles ne sont injectées **que pour un document dont le contexte déclare la juridiction `EU`** : sans déclaration, ou pour une autre juridiction, elles sont écartées. Ce comportement est voulu et testé.

**La paire arabe** (Wikidata, domaines EuroVoc) fonctionne comme EuroVoc. Elle ne couvre que 43 % des descripteurs retenus. 70 descripteurs jugés incorrects par au moins un des deux évaluateurs automatiques sont placés dans `data/rag-ue/wikidata/revue-evaluation-automatique.csv` : ils ne sont pas importables tant qu’une personne n’a pas tranché.

**Les textes intégraux EUR-Lex** (`data/rag-ue/eurlex/eurlex/`) sont chargés dans la bibliothèque commune comme référentiel réglementaire : tables `rag_legal_texts` (un texte par couple acte-langue) et `rag_legal_passages` (un passage par article). Ils sont consultables en lecture seule par `legal-search`, uniquement une fois publiés et actifs. La recherche porte sur des mots entiers (un mot composé n’est trouvé que sous sa forme complète). Le Journal officiel écrit parfois l’allemand sans tréma (« Hoechstarbeitszeit » dans la directive 2003/88/CE) : une requête essaie donc aussi l’autre graphie, que la réponse signale dans `spelling_variants`, sans que le texte officiel soit modifié. Ils ne sont **jamais injectés dans une traduction** : le moteur DICE ne lit que les référentiels terminologiques, et aucun index BM25 ni entrée terminologique n’est créé pour eux. Il s’agit du texte initial publié au Journal officiel, **non consolidé** : les modifications ultérieures d’un acte n’y figurent pas. L’utilisation de ces passages dans la traduction (citation de l’article applicable, par exemple) relève du LOT 3, qui n’est pas engagé sans validation explicite.

Ces données n’apportent aucun vectoriel ni aucune recherche sémantique (ni Qdrant ni BGE-M3). L’appariement reste lexical : forme exacte, synonymes, clés d’alias par langue (dont l’article défini attaché en maltais). Le gain attendu concerne la **cohérence terminologique**. Il n’a pas encore été mesuré sur des traductions réelles ; une telle mesure suppose le moteur cible et une relecture humaine.

## Contrôles avant publication (relecteur)

Avant de valider une version, le relecteur vérifie les points suivants.

1. **Rapport d’import.** Il doit contenir 0 erreur. Les avertissements sont à relire : doublons, collisions de synonymes et cibles concurrentes.
2. **Échantillon de lignes.** Le relecteur contrôle quelques lignes dans chaque domaine utile au tenant : terme source, terme français, provenance (CELEX ou EuroVoc).
3. **Définitions.** Le terme français doit correspondre à l’usage du tenant. Une définition légale de l’UE n’est pas toujours le terme du droit national applicable.
4. **Anomalies déclarées.** Le relecteur prend connaissance des anomalies de `data/rag-ue/eurlex/manifest.json` (3 couples acte-langue).
5. **Évaluation automatique.** Les résultats de l’évaluation par deux modèles (section correspondante de `data/rag-ue/README.md`) orientent la relecture ; ils ne la remplacent pas. Pour l’arabe, le relecteur tranche aussi les 70 descripteurs de la liste de revue.

## IATE

IATE est la base terminologique de référence des institutions de l’UE, mais son export ciblé exige un compte EU Login. Il appartient à l’exploitant de produire l’export (TBX), puis de le convertir :

```bash
python tools/rag_ue/iate_tbx_to_csv.py --tbx export.tbx --export-date 2026-11-03 --domain HR \
    --out /chemin/iate-hr
python -m app.rag.common_library_cli import --name "IATE HR de-fr" --languages de,fr \
    --actor alice /chemin/iate-hr/iate-de-fr.csv
```

Le convertisseur ne retient que les termes de fiabilité IATE au moins égale à 3 (réglable avec `--min-reliability`), non dépréciés, non remplacés et non obsolètes. Pour chaque ligne, il trace la fiche, la fiabilité et la date de l’export.
