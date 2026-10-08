# Guide utilisateur

## Se connecter

Ouvrir l’URL privée via TLS et se connecter avec un compte fourni par l’administrateur. Le tenant est déterminé par le jeton; un identifiant de document d’un autre tenant doit rester inaccessible. Ne jamais partager un token bearer.

## Importer et analyser

1. Aller à **Upload**, choisir un PDF ou DOCX autorisé et confirmer qu’il ne contient que des données approuvées.
2. Attendre `ANALYZING`, puis vérifier pages, langue, type, blocs, avertissements et previews.
3. Lire les alertes OCR : scan, écriture, cachet, signature, tableau, RTL, page inconnue ou langue mixte ne sont pas des garanties de lecture.

L’IR conserve l’ordre et les coordonnées. La détection automatique de zéro tableau n’annule pas une grille visible; demander une revue lorsque la structure est incertaine.

## Traduire

Choisir la langue cible et le glossaire du tenant. `offline` réutilise uniquement une mémoire/glossaire validé; un segment inconnu est conservé et marqué `UNTRANSLATED`. `private` appelle seulement l’endpoint privé autorisé. Si le modèle ou le tokenizer ne sont pas disponibles, le document reste à revoir : aucune traduction publique ni fausse réussite n’est produite.

## Revoir et comparer

Dans **Review**, examiner page par page les panneaux original, candidat traduit et diff. Vérifier chiffres, dates, références, mentions juridiques, tableaux, champs, signatures/cachets, ordre RTL, pagination et débordements. Les corrections sont explicites par bloc; les régions protégées et entités sensibles doivent être déclarées.

`layout_score` décrit la géométrie, pas le sens. Une métrique `Non mesuré`/`null` signifie qu’aucune référence humaine validée ne permet de conclure.

## Approuver ou rejeter

- **Approve** exige le rôle requis, une attestation de revue, une revalidation sans erreur critique, sans segment inconnu et sans débordement.
- **Reject** conserve la raison et laisse le document non final.
- **Correct** crée une nouvelle candidate; aucune correction implicite n’est appliquée lors de l’approbation.
- **Promote Golden** est optionnel, versionné et audité; il ne doit être choisi qu’après validation humaine indépendante.

Le fichier `final` n’est téléchargeable qu’après `APPROVED`. Les originaux restent immuables.

## Glossaire et mémoire

Un glossaire est tenant-scoped (`source`, `target`, domaine, version). La mémoire n’accepte qu’une entrée validée par un reviewer. Ne pas y déposer de texte sensible non autorisé; l’audit ne conserve pas les contenus.
