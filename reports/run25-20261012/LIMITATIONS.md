# RUN25 — Limitations

Ce document recense les limites qui subsistent après run25, chiffrées sur le run final (run25e, code
`f4a84aaef38c7c7d`), avec leur cause quand elle est établie et la piste de traitement. Aucune n'est masquée par un
statut favorable : les 8 documents sont `REVIEW_REQUIRED`.

## 1. Validation et références

| Limite | Effet |
|---|---|
| Aucune référence humaine (traduction ou OCR) | L'exactitude des traductions n'est **pas mesurée**. Aucune métrique CER, WER, BLEU ou équivalente n'est calculée ni présentée. |
| Qualification bancaire ou métier | **Non validée.** |
| Qwen / vLLM privé | `NOT_AVAILABLE` : point de terminaison, tokeniseur et poids non fournis. Les résultats Interim ne valent pas validation de Qwen. L'abstraction est conservée, sans repli public automatique. |
| Fidélité des tableaux | **Non mesurée par le moteur** (`no_real_table_detected` sur les 8 scans). Scores `STRUCTURE`, `TABLE`, `ENTITY` et `GLOBAL` à `NULL`. |
| Tests de bout en bout de l'écran de revue dans un navigateur | Non exécutés. |

## 2. Moteur IA temporaire (Interim)

* **Variance de génération.** À source identique, 71,6 % des caractères (333 blocs sur 1 072) reçoivent une cible
  différente d'un passage à l'autre. L'écart de couverture écrite par document atteint −0,241 (DOC-005).
  * Le verdict repose donc sur la mémoire de traduction de run24 : la qualité de ces traductions est celle de cette
    génération.
  * Une nouvelle génération peut donner un résultat différent.
* **Sources renvoyées inchangées** (`FAILED:model_returned_source`) : DOC-007 537 caractères, DOC-008 388,
  DOC-004 264, DOC-005 93.
  * En DOC-008, ce sont des noms, adresses, sociétés et domaines : la conservation est correcte, mais le moteur la
    classe `FAILED`, faute d'un détecteur de noms propres assez large.
  * Ailleurs, il s'agit d'OCR illisible et de noms propres, et le retry existant ne récupère pas ces blocs.
* **Budget de 32K** : respecté (0 violation, réservation maximale de 22 467 tokens). Le contrat de complétion
  (8 000 tokens, raisonnement inclus) provient de la documentation publique de l'API, et le contrôle après usage est
  fail-closed.
* **Autorisation du propriétaire** : liée à la liste des empreintes SHA-256 des originaux, conservée hors Git et
  expirante. Toute relance doit la revalider.

## 3. Rendu dans le PDF

| Limite | Volume (run25) | Cause | Piste |
|---|---|---|---|
| Débordements refusés (`LAYOUT_OVERFLOW`) | 29 : DOC-004 14, DOC-007 8, DOC-006 3, DOC-001 2, DOC-008 2 | DOC-004 : lignes arabes en cellule, cible 1,2 à 2 fois plus longue, police au plancher de 72 % ; DOC-007 : source plus large que sa boîte à la police de rendu (scan condensé) | police condensée ou mise en page alternative (renvoi, annexe) ; le plancher de police n'est pas abaissé |
| Refus « encre résiduelle » | 9 blocs : DOC-004 3, DOC-007 3, DOC-002 1, DOC-005 1, DOC-006 1 | encre d'une région protégée ou d'un voisin non séparable au creux | refus sûr conservé |
| Masques trop grands (`VISUAL_MASK_TOO_LARGE`) | DOC-006 12, DOC-007 2, DOC-004 1 | masques couvrant une part importante de la zone | revue humaine |
| Mise en forme RTL non prise en charge | DOC-004 : 47 caractères | façonnage de l'arabe non disponible dans le moteur de rendu | moteur de façonnage (HarfBuzz) |
| Encre originale effacée hors des blocs écrits | **6 573 px**, 129 grappes : DOC-006 3 330, DOC-004 1 743, DOC-008 809, DOC-007 517, DOC-005 87, DOC-001 73, DOC-002 14 | marge des masques sur une encre que F24 ne sait pas départager | analyse grappe par grappe |
| Filet aminci | DOC-004 `p001-b0106` (95 px) | filet de 0,3 pt touché par le masque : régression mineure de F24, filet encore visible | critère de filet fin |
| Régions graphiques altérées | 81, toutes sous un bloc traduit et écrit, localisées dans l'export | changement attendu en général ; non vérifié visuellement une par une | revue humaine |
| Titre trop large | DOC-007 `p001-b0038` | rendu à la taille du corps, en gras, plus large que l'original condensé (confiance OCR inférieure au seuil de taille propre) | esthétique, sans perte |
| Traduit et placé mais introuvable dans le PDF | DOC-004 : 45 caractères absents, 99 partiels | non établie : mesure ou rendu | à instruire |

## 4. OCR

| Limite | Volume (run25) | Effet |
|---|---|---|
| Traductions d'une OCR de faible confiance, écrites | 48 blocs : DOC-007 23, DOC-004 20, DOC-006 3, DOC-002 1, DOC-008 1 | une ligne illisible peut être traduite comme un texte valide (mot ou nombre inventé) ; le seuil de confiance n'a pas été durci |
| Blocs conservés pour OCR non fiable (`UNCERTAIN:ocr_unreliable`) | 77 : DOC-004 45, DOC-006 20, DOC-007 6, DOC-002 2, DOC-005 2, DOC-008 2 | non traduits, original conservé ; comptés dans la catégorie « non lisible », bien que certains soient lisibles mais non fiables (cases, numéros RTL) |
| Ordre des groupes de chiffres en contexte RTL (F23) | 3 lignes détectées | heuristique : un numéro à groupe unique, ou dans un contexte RTL sans lettres ni marques bidi, n'est pas détecté |
| Cases mal lues sans case détectée (F21) | 1 ligne détectée | motif strict de jetons : une autre forme de case mal lue n'est pas détectée |
| Langue par preuve lexicale (`wordfreq`) | — | la licence CC-BY-SA-4.0 des données est à valider avant distribution ; sans `wordfreq`, le reclassement est désactivé |

## 5. Données critiques

* Alertes d'entités maintenues :
  * DOC-006 : `CRITICAL_ENTITY_MODIFIED` ×2, `HALLUCINATION_ENTITY_MODIFIED`, `HALLUCINATION_UNIT_CHANGED`,
    `PROTECTED_ENTITY_CHANGED`, et 97 lignes au registre ;
  * DOC-002 et DOC-007 : `PROTECTED_ENTITY_CHANGED` ×1 chacun.

  Elles bloquent la validation automatique, et seule une revue humaine peut les lever.
* Le contrôle indépendant des séquences de chiffres (159 blocs) ne trouve aucune altération. Il ne couvre ni les
  dates écrites en lettres, ni les noms, ni les montants sans chiffres.
* DOC-007 : un tableau réel n'est relié à aucun bloc (`UNMAPPED_TABLE_CONTENT`). Son contenu n'est pas rattaché à
  la structure de tableau.

## 6. Revue humaine

* L'écran de revue liste les problèmes par bloc (sévérité, message) et les blocs non traduits, avec les actions
  approuver, rejeter et corriger, et affiche les aperçus original, traduit et différence.
* Il **n'affiche pas, par zone, la page, le cadre ni la traduction proposée**, alors que ces informations existent
  dans `translation.json` et dans le registre d'anomalies. Le relecteur doit donc retrouver la zone lui-même.
  L'exigence du §3 (« résultat exploitable pour la revue humaine ») n'est que **partiellement** remplie.
* Piste : exposer `page` et `bbox` dans les problèmes de l'API de revue et surligner la zone dans l'aperçu.

## 7. Méthode de recette

* La mesure de rendu repose sur l'extraction du texte inséré. Un bloc écrit mais illisible (chevauchement visuel sans
  collision de mots) n'est pas détecté par la mesure, seulement par l'inspection visuelle, qui n'a pas couvert toutes
  les pages (liste dans `RUN25_DOCUMENT_FIDELITY_REPORT.md` §2).
* Le seuil d'altération des régions (2 % des pixels) et la détection des régions candidates sont heuristiques.
* La relecture instrumentée privée contourne le filtre `ocr_unreliable` du service. Les conclusions F21 et F23
  reposent donc sur les vrais runs.
* La baseline de DOC-003 (0) n'est pas comparable : elle réécrivait du français hors périmètre.
* Les valeurs du 09/10 ne sont pas comparables à celles de run18 et run25 : la règle du dénominateur a changé.
