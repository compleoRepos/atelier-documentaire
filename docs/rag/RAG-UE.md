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

# 3. Cycle de validation (validation par une autre personne)
python -m app.rag.common_library_cli transition --name "EUR-Lex définitions de-fr" --version 1 \
    --action submit --actor alice
python -m app.rag.common_library_cli transition --name "EUR-Lex définitions de-fr" --version 1 \
    --action validate --actor bob
python -m app.rag.common_library_cli transition --name "EUR-Lex définitions de-fr" --version 1 \
    --action publish --actor alice
python -m app.rag.common_library_cli activate --name "EUR-Lex définitions de-fr" --actor alice

# État de la bibliothèque commune
python -m app.rag.common_library_cli status
```

Un référentiel est créé par paire de langues, car l’API limite à 20 le nombre de langues déclarées par référentiel. Ce plafond est inférieur aux 25 langues désormais acceptées ; il n’a pas été modifié, pour préserver le contrat de l’API.

## Ce que ces données apportent, et ce qu’elles n’apportent pas

Les deux types de données n’ont pas la même portée.

**EuroVoc** (domaines `HR`, `PAYROLL`, `BANKING`, `FINANCE`, `TAX`, `INSURANCE`, `LEGAL`, `ADMINISTRATION`, sans juridiction) fournit l’équivalent français institutionnel d’un terme reconnu dans le document source. Ce terme est injecté dans la consigne du moteur pour les documents d’un domaine compatible.

**Les définitions EUR-Lex** (domaine `HR`, juridiction `EU`) fournissent le terme français employé par la version française de la directive. Elles ne sont injectées **que pour un document dont le contexte déclare la juridiction `EU`** : sans déclaration, ou pour une autre juridiction, elles sont écartées. Ce comportement est voulu et testé.

**Les textes intégraux EUR-Lex** (`data/rag-ue/eurlex/eurlex/`) constituent la base de contenu juridique. Ils ne sont **pas** chargés dans le produit : la recherche de passages juridiques (tables `rag_legal_texts` et `rag_legal_passages`, vides) relève du LOT 3, qui n’est pas engagé sans validation explicite.

Ces données n’apportent aucun vectoriel ni aucune recherche sémantique (ni Qdrant ni BGE-M3). L’appariement reste lexical : forme exacte, synonymes, clés d’alias par langue (dont l’article défini attaché en maltais). Le gain attendu concerne la **cohérence terminologique**. Il n’a pas encore été mesuré sur des traductions réelles ; une telle mesure suppose le moteur cible et une relecture humaine.

## Contrôles avant publication (relecteur)

Avant de valider une version, le relecteur vérifie les points suivants.

1. **Rapport d’import.** Il doit contenir 0 erreur. Les avertissements sont à relire : doublons, collisions de synonymes et cibles concurrentes.
2. **Échantillon de lignes.** Le relecteur contrôle quelques lignes dans chaque domaine utile au tenant : terme source, terme français, provenance (CELEX ou EuroVoc).
3. **Définitions.** Le terme français doit correspondre à l’usage du tenant. Une définition légale de l’UE n’est pas toujours le terme du droit national applicable.
4. **Anomalies déclarées.** Le relecteur prend connaissance des anomalies de `data/rag-ue/eurlex/manifest.json` (3 couples acte-langue).

## IATE

IATE est la base terminologique de référence des institutions de l’UE, mais son export ciblé exige un compte EU Login. Il appartient à l’exploitant de produire l’export (TBX), puis de le convertir :

```bash
python tools/rag_ue/iate_tbx_to_csv.py --tbx export.tbx --export-date 2026-11-03 --domain HR \
    --out /chemin/iate-hr
python -m app.rag.common_library_cli import --name "IATE HR de-fr" --languages de,fr \
    --actor alice /chemin/iate-hr/iate-de-fr.csv
```

Le convertisseur ne retient que les termes de fiabilité IATE au moins égale à 3 (réglable avec `--min-reliability`), non dépréciés, non remplacés et non obsolètes. Pour chaque ligne, il trace la fiche, la fiabilité et la date de l’export.
