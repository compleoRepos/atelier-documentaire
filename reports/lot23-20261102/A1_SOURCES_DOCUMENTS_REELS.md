# Sources légales de documents réels remplis pour qualifier une plateforme de dossiers de crédit

| | |
|---|---|
| Lot / phase | LOT 2.3 — Phase A, complément documentaire (consigne §3.1) |
| Date | 1er novembre 2026 |
| Résultat | **Aucun document réel rempli et légalement exploitable n’a été obtenu.** Ce constat est signalé explicitement ; aucune pièce synthétique n’a été substituée à une pièce réelle. |
| Méthode | Recherche de pages publiques uniquement : aucun téléchargement de document ou de jeu de données, aucun contournement d’accès restreint, aucune donnée personnelle reproduite. |
| Vérification | Trois affirmations ont été revérifiées directement à la source le 1er novembre 2026 : licence XFUND (CC BY-NC-SA 4.0) [2], délais CNDP (récépissé sous 24 h, avis d’autorisation sous 2 mois prorogeable une fois, transfert à l’étranger subordonné à un traitement déclaré ou autorisé) [21], délais Bank Al-Maghrib (voir la correction ci-dessous) [23]. Les autres lignes reposent sur la lecture des pages citées et restent à confirmer par un juriste avant tout usage. |

## Périmètre et règle de classement

Ce recensement porte sur des pages publiques consultées, sans téléchargement de document ni de jeu de données. Les catégories sont appliquées ainsi : **R** = document réel rempli ; **RA** = document réel anonymisé, caviardé ou flouté ; **S** = document synthétique ou généré ; **M** = modèle ou formulaire vierge. Une licence non formulée explicitement par la source est indiquée comme **« licence non explicite »**. Une licence de code ou de métadonnées n’est pas assimilée à une autorisation de réutiliser les images documentaires.

## 1. Jeux de données publics

| Nom | Nature R/RA/S/M | Types de documents | Langues | Volume | Licence exacte | Usage commercial | Données personnelles | Pertinence pour le dossier de crédit | URL |
|---|---|---|---|---:|---|---|---|---|---|
| FUNSD | **R** | Formulaires scannés remplis, annotations de mots, entités et relations | Langue principalement anglaise dans la description consultée | 199 formulaires, 31 485 mots, 9 707 entités, 5 304 relations | Conditions d’utilisation FUNSD : usage exclusivement non commercial, recherche et éducation ; images soumises aux droits et autorisations éventuellement nécessaires | **Non** pour l’usage commercial, d’après les conditions | Oui, potentiellement ; la source dit que les images sont des formulaires réels et renvoie à RVL-CDIP pour les images | Moyenne pour mise en page, OCR et formulaires ; faible pour relevés, salaires ou crédit | [1] |
| XFUND | **R** | Formulaires multilingues annotés avec paires clé-valeur | Chinois, japonais, espagnol, français, italien, allemand, portugais | Statistiques par langue publiées ; par exemple 183 formulaires d’entraînement et 66 de test en français ; total exact de formulaires non résumé sur la page | **CC BY-NC-SA 4.0** pour le projet | **Non** : la clause NC exclut l’usage commercial | Présence possible de données identifiantes dans des formulaires réels ; la page ne donne pas de garantie d’anonymisation | Moyenne : utile pour français/italien/allemand/espagnol et variantes de formulaires, mais pas bancaire | [2] |
| RVL-CDIP / IIT-CDIP | **R** | Lettres, mémos, courriels, formulaires, factures, budgets, questionnaires, CV, rapports et autres documents complexes | Langue non spécifiée dans la fiche consultée | 400 000 images en niveaux de gris, 16 classes ; 320 000 entraînement, 40 000 validation, 40 000 test | La fiche indique que RVL-CDIP est un sous-ensemble d’IIT-CDIP, lui-même issu de la Legacy Tobacco Document Library ; **licence propre du jeu non explicite** sur la page | **Non déterminable** : vérifier les conditions de la source primaire et les droits sur chaque image avant tout usage commercial | Risque élevé : documents réels issus d’archives industrielles ; aucune garantie d’anonymisation affichée | Faible à moyenne pour robustesse OCR et classification ; faible pour crédit immobilier marocain | [3] |
| DocVQA – tâche 1 | **R** | Pages de documents issus de l’UCSF Industry Documents Library, questions-réponses et transcriptions OCR | Anglais | La page décrit des fichiers d’images et d’annotations par train/validation/test, sans total global dans le texte consulté | **Licence non explicite** ; téléchargement conditionné à une connexion au portail RRC et à l’acceptation des conditions | **Non déterminable** ; accès restreint et conditions à lire avant usage | Oui, risque élevé : documents réels ; la page expose des réponses textuelles et ne garantit pas une anonymisation générale | Faible à moyenne pour OCR et questions sur documents ; faible pour priorité bancaire | [4] |
| Kleister Charity | **R** | Rapports financiers annuels de fondations et associations britanniques ; revenus, dépenses, dates et adresses d’organisations | Anglais après filtrage ; la publication indique que les documents non anglais ont été retirés | 2 788 rapports, 61 643 pages, 21 612 entités ; dépôt public réparti en 1 729/440/609 documents | **Licence non explicite** dans le dépôt et la publication consultés ; documents provenant de rapports publiés par la Charity Commission | **Non déterminable** ; obtenir une permission distincte pour la redistribution ou l’intégration commerciale | Données d’organisations et adresses publiées ; présence possible de noms de dirigeants ou de signataires ; pas de garantie d’anonymisation | Moyenne pour rapports financiers et documents longs ; faible pour relevés ou bulletins de salaire | [5] [6] |
| CORD | **R** | Reçus de magasins et restaurants, images, boîtes et textes OCR, annotations sémantiques | Indonésien | Plus de 11 000 reçus annoncés ; versions publiques v1/v2 de 1 000 échantillons, avec 800/100/100 train/dev/test | **CC BY 4.0** | **Oui en principe**, sous réserve des droits sur les contenus et du respect de l’attribution ; la page signale aussi le retrait de certaines catégories pour raisons juridiques indonésiennes | Des champs sensibles ont été retirés dans la version publiée ; aucune garantie que tout contenu restant soit anonyme | Faible à moyenne : utile pour OCR de pièces commerciales et montants, pas pour crédit | [7] |
| FinTabNet.c | **R** | Tables financières extraites de rapports annuels, avec annotations de structure de tableaux | Anglais dans la source d’origine ; distribution linguistique complète non indiquée | La fiche consultée indique un fichier d’environ 3,43 Go, sans nombre de lignes exploitable dans la page | **CDLA-Permissive-2.0** indiquée par la fiche ; cette licence autorise l’utilisation, la modification et le partage sous réserve de rendre le texte de la licence disponible | **Oui selon les permissions de la CDLA-Permissive-2.0**, mais vérifier les droits de source des rapports et la fiche de la version effectivement utilisée | Risque de données d’entreprises et de personnes mentionnées dans les rapports ; anonymisation non garantie | Moyenne pour tableaux financiers et OCR de rapports ; faible pour relevés et pièces marocaines | [8] [9] |
| SROIE | **RA** | Reçus et factures scannés, OCR et extraction de nom, adresse, téléphone et total | Principalement anglais dans la description publique ; autres langues non garanties | La page de la compétition décrit un corpus de reçus annotés ; le nombre de 973 est utilisé dans la publication Kleister, mais n’est pas répété sur la page RRC consultée | **Licence non explicite** sur la page officielle consultée | **Non déterminable** ; conditions de compétition et droits de source à vérifier | **Réels mais partiellement caviardés** : la page dit que des champs sensibles tels que nom, adresse et contact sont floutés | Faible à moyenne pour reçus, OCR et données chiffrées ; faible pour crédit | [10] |
| DocILE – documents annotés | **R** | Documents commerciaux semi-structurés, notamment factures et commandes ; localisation d’informations et lignes d’articles | Langue non détaillée dans la page consultée | 6 680 documents annotés dans l’ensemble DocILE annoncé | **Licence non explicite** ; accès sur demande pour la recherche, avec information sur le traitement de données dans le cadre de la recherche | **Non déterminable et non recommandé** sans accord écrit ; le dispositif est présenté comme accès de recherche | Documents d’entreprise ; la page renvoie à une information légale sur les données personnelles et ne promet pas l’absence d’identifiants | Faible à moyenne pour factures et tableaux ; faible pour dossiers de crédit | [11] |
| DocILE – documents synthétiques | **S** | Documents commerciaux générés, notamment factures et commandes | Non détaillée | 100 000 documents synthétiques annoncés | **Licence non explicite** sur la page consultée ; accès sur demande pour la recherche | **Non déterminable** | Pas de personnes réelles attendues par construction, mais contrôler la fiche avant tout usage | Faible pour le besoin prioritaire, utile seulement pour pré-calibrage | [11] |
| NIST Special Database 2 / SFRS | **S** | Formulaires fiscaux complétés simulés, réponses de champs, formes structurées | Anglais, formulaires fiscaux des États-Unis | 900 soumissions simulées ; 5 590 images de faces de formulaires et 5 590 fichiers de réponses | La page NIST décrit le corpus et renvoie à une licence ouverte NIST ; **texte de licence non consulté ici, donc licence non explicite dans ce rapport** | **Non déterminable** sans vérifier la licence NIST applicable | Non : la source précise que les images ont l’apparence de formulaires réels mais sont automatiquement dérivées et synthétisées | Faible : bon test de formulaires et montants fiscaux, mais pas de documents réels | [12] |
| Sinabis 1K Synthetic PDF | **S** | Bulletins de salaire, relevés bancaires, reçus, factures, attestations et autres documents commerciaux synthétiques | 23 langues indiquées dans la fiche ; plusieurs devises et pays | 1,01 k lignes/documents | **CC BY 4.0** indiquée dans la fiche | **Oui en principe**, sous attribution ; la licence ne transforme pas le corpus en documents réels | La fiche se présente comme synthétique ; elle indique que les entités et identifiants sont générés, mais il faut tout de même contrôler chaque version | Faible pour la qualification finale ; utile pour tests de formats de bulletins et relevés, jamais comme preuve de réalisme bancaire | [13] |
| Receipts, Invoices & Bank Statements Dataset | **Exclu du tableau de qualification** | Reçus, factures et relevés bancaires selon la fiche | Non suffisamment documentées | 150 000 annoncés, dont 50 000 relevés bancaires | **Licence à préciser par le mainteneur** | **Non** tant que la licence et les droits de redistribution ne sont pas précisés | La fiche indique que la provenance peut être synthétique, publique ou autorisée, sans établir quelle catégorie s’applique à chaque fichier ; elle demande de vérifier autorisations et caviardage | Ne peut pas être retenu comme source légale de documents réels sans provenance et licence vérifiables | [14] |
| Formulaires et produits ANCFCC | **M** | Formulaires de formalités foncières, descriptions de duplicata et certificats ; pas de dossier individuel fourni | Français et arabe selon les pages | Non indiqué | **Licence non explicite** pour la réutilisation des formulaires et pages | **Non déterminable** | Pas de dossier individuel dans les pages consultées ; les certificats réels sont délivrés au propriétaire ou mandataire | Moyenne pour gabarits de titres, certificats et hypothèques ; aucune valeur pour tester des données remplies | [15] [16] |

### Lecture opérationnelle du tableau

Les sources les plus proches du besoin de documents remplis sont FUNSD, XFUND, RVL-CDIP, DocVQA, Kleister Charity, CORD, FinTabNet.c et SROIE, mais elles ne constituent pas un substitut à un accord bancaire. Les seules sources publiques examinées qui couvrent explicitement des bulletins de salaire ou des relevés bancaires sont synthétiques ou de provenance incertaine. Le corpus public ne fournit donc pas, à lui seul, un lot juridiquement sûr de relevés bancaires réels marocains ou de bulletins de salaire réels anonymisés.

## 2. Publications officielles contenant des documents réels anonymisés ou caviardés

### Décisions judiciaires françaises : portée limitée

La base Judilibre de la Cour de cassation met gratuitement à disposition des décisions publiques, éventuellement enrichies et **pseudonymisées** ; depuis 2022, elle inclut aussi des décisions civiles, sociales et commerciales des cours d’appel. [17] Cette voie peut fournir du texte juridique réel et certaines mentions financières, mais elle ne met pas à disposition les pièces originales du dossier : la décision publiée n’est pas un paquet de pièces bancaires, de bulletins de salaire, de relevés ou d’actes notariés. Elle est donc utile pour tester une décision et ses annexes textuelles seulement si elles sont effectivement publiées, pas pour constituer un corpus de pièces justificatives.

La pseudonymisation ne doit pas être traitée comme une anonymisation. La CNIL définit l’anonymisation comme un procédé irréversible rendant l’identification impossible en pratique ; elle distingue cette situation de la pseudonymisation, qui conserve un caractère personnel lorsqu’une information supplémentaire ou des données tierces peuvent relier le document à une personne. [18] Judilibre doit donc être classé comme publication pseudonymisée, non comme ensemble garanti de documents anonymes.

### Rapports et registres officiels

Le registre britannique des associations caritatives permet une recherche gratuite de données publiques sur l’organisation, ses finances et ses rapports. [19] La Charity Commission met aussi à disposition un extrait quotidien de données publiques sous Open Government Licence v3.0, sauf indication contraire. [20] Cela peut fournir des rapports financiers réels d’organisations, comme dans Kleister Charity, mais pas des documents de revenus de particuliers ni des relevés bancaires. Les noms et adresses d’organisations restent des données publiées ; il faut vérifier séparément les éventuelles personnes physiques présentes dans les PDF.

Aucune page officielle consultée n’établit que les autorités marocaines publient en accès libre des relevés bancaires, bulletins de salaire, tableaux d’amortissement ou dossiers de crédit réels anonymisés. Les pages ANCFCC décrivent les produits et formalités, mais les certificats réels sont délivrés au propriétaire ou à son mandataire ; elles ne publient pas un jeu de dossiers individuels réutilisable. [15] [16]

## 3. Voies d’obtention autorisées au Maroc

### CNDP et loi 09-08

La CNDP indique que tout traitement doit faire l’objet d’une déclaration préalable, sauf exclusion, dispense ou régime d’autorisation préalable. Elle fournit les formulaires de déclaration simplifiée et normale, demande une habilitation du signataire et annonce un récépissé sous 24 heures pour une déclaration complète. [21]

Une autorisation préalable est notamment requise en cas de changement de finalité, d’utilisation du numéro de la carte d’identité nationale, de données sensibles ou d’interconnexion de fichiers à finalités différentes. La CNDP demande alors les éléments d’information des personnes, les justificatifs de consentement lorsque nécessaire, les clauses de sous-traitance et les mesures de sécurité ; elle indique un délai de deux mois, prorogeable une fois, pour son avis. [21] [22]

Pour un test alimenté par des dossiers de crédit existants, le dossier à préparer devrait au minimum préciser la finalité de qualification, les catégories de documents et de personnes, les opérations OCR/traduction/analyse, la durée de conservation, les accès, les suppressions, les contrôles de ré-identification, la convention avec la banque et la procédure de restitution ou destruction. Une pseudonymisation réversible ne dispense pas de la loi 09-08. La CNDP exige aussi une demande distincte si les données personnelles sont hébergées ou transmises à l’étranger ; l’autorisation de transfert suppose que le traitement sous-jacent ait déjà été déclaré ou autorisé. [21]

### Bank Al-Maghrib et le parcours fintech

Le guide officiel de Bank Al-Maghrib présente un parcours de contact, de consultation réglementaire, d’avis sur un projet et, lorsque nécessaire, de demande d’agrément. La Direction de la Supervision Bancaire est le point de contact pour les projets de services bancaires ; le guide indique l’adresse de contact et précise que la Banque peut renseigner sur la réglementation, orienter vers d’autres autorités et suivre les démarches. [23]

Le guide annonce une réunion sous deux jours pour les questions réglementaires (§4.2), une réunion de présentation du projet sous deux semaines, **puis** un retour écrit sous deux semaines après cette réunion, ou l’annonce d’un délai supplémentaire (§4.3). Ces délais concernent le dialogue réglementaire, pas l’obtention d’échantillons. La demande d’agrément, lorsqu’elle est nécessaire, est instruite dans un délai maximal de quatre mois après réception d’un dossier complet. [23]

La voie réaliste est de demander à Bank Al-Maghrib une orientation écrite vers le cadre approprié, puis de faire porter la mise à disposition des documents par une banque participante, dans une convention séparée. Le guide rappelle que la protection des consommateurs et des données personnelles fait partie des éléments examinés dans une demande d’agrément. [23]

### GPBM et établissements bancaires

Le GPBM est identifié dans une publication officielle de Bank Al-Maghrib comme le groupement professionnel des banques du Maroc. La page consultée documente le lancement, par le GPBM sous l’impulsion de Bank Al-Maghrib, d’un comparateur public de tarifs et dates de valeur ; elle ne crée pas de procédure publique de remise de relevés ou dossiers de crédit. [24]

Il faut donc traiter le GPBM comme une voie de mise en relation et de normalisation sectorielle, non comme une licence de réutilisation. La demande devrait viser des banques volontaires et proposer deux niveaux : d’abord des copies réelles caviardées contrôlées par la banque, puis, si nécessaire, une qualification en environnement fermé sans remise du fichier original. Les pièces à prévoir sont une convention de mise à disposition, une annexe de périmètre, un protocole de caviardage, une matrice de champs conservés, une durée de conservation, des mesures de sécurité, un registre des accès et un procès-verbal de destruction.

### ANCFCC

L’ANCFCC décrit le duplicata du titre foncier comme un document conforme au livre foncier et le certificat de propriété comme attestant la situation juridique et matérielle d’un immeuble au moment de la demande. Elle précise que ces documents sont délivrés au propriétaire ou à son mandataire. [15] La procédure d’immatriculation mentionne les actes, documents de propriété, procès-verbaux, plans et pièces produits par les parties, mais ne prévoit pas une bibliothèque ouverte d’exemples individuels réutilisables. [16]

La demande utile est donc une demande de **spécimens non individualisés**, de maquettes ou de copies caviardées validées par l’ANCFCC, et non une extraction de certificats réels. Pour des tests de crédit immobilier, l’ANCFCC peut être sollicitée sur les champs et la structure attendus ; un dossier bancaire séparé reste nécessaire pour des titres effectivement remplis.

### Conseil National de l’Ordre des Notaires du Maroc

Le site officiel du CNONM se présente comme l’organe habilité à s’exprimer au nom de la profession notariale et publie un formulaire de contact, une adresse, un téléphone et une adresse électronique institutionnels. [25] [26] Le site décrit le rôle du notaire dans les actes et formalités, mais les pages consultées ne publient pas de lot d’actes notariés individuels anonymisés avec licence de réutilisation.

La voie à proposer est un partenariat avec le CNONM et un ou plusieurs notaires volontaires pour fournir des actes réels caviardés ou des jeux de copies conservés sur site. La convention doit interdire toute reconstitution de l’identité, encadrer les sceaux et signatures, préciser les droits sur les modèles et régler la destruction des copies.

## 4. Voies équivalentes en Europe

Le RGPD distingue clairement l’anonymisation irréversible de la pseudonymisation. La CNIL indique que des données anonymisées ne relèvent plus de la législation sur la protection des données, tandis que les données pseudonymisées restent personnelles. Elle recommande d’évaluer l’individualisation, la corrélation et l’inférence, et de tenir compte des moyens raisonnablement susceptibles d’être utilisés pour réidentifier. [18]

La CNIL recommande, pour un protocole de recherche, d’associer le délégué à la protection des données et de rédiger le protocole de façon concertée. Elle présente la pseudonymisation comme une mesure de réduction des risques, pas comme une suppression des obligations. [27] Le CEPD rappelle de même que la pseudonymisation réduit la possibilité de relier des données à une personne sans viser à couper complètement ce lien ; seules les données véritablement anonymisées sortent du champ de la protection des données de l’Union. [28]

Le « bac à sable » de la CNIL est un accompagnement renforcé et temporaire pour des projets sélectionnés. Il ne lève aucune contrainte du RGPD et ne fournit pas une infrastructure informatique de test. Le dossier de candidature décrit notamment les objectifs, flux de données, risques, maturité du projet, questions juridiques et engagement de conformité. [29] Il peut aider à cadrer un projet de qualification documentaire, mais il ne remplace ni le consentement ou autre base légale, ni un accord de mise à disposition avec une banque, ni une autorisation de transfert depuis le Maroc.

Pour les établissements européens, la demande la plus sûre est un test fermé : la banque reste responsable de la sélection et du caviardage, conserve la table de correspondance hors du périmètre, impose une finalité de test, interdit l’enrichissement externe, journalise les accès, limite la conservation et contrôle la destruction. Une analyse d’impact doit être envisagée si les opérations présentent un risque élevé, notamment par croisement de relevés, revenus, dettes et informations patrimoniales.

## 5. Recommandation pratique : huit voies réalistes

| Voie | Réalisme | Effort et délai indicatif | Risques juridiques | Pièces à préparer |
|---|---|---|---|---|
| 1. Pilote avec une banque marocaine volontaire via le GPBM | Très élevé pour relevés, bulletins, attestations, tableaux d’amortissement et crédits | Effort élevé ; délai **non documenté** par les sources publiques | Données financières et de crédit, secret bancaire, finalité secondaire, transfert éventuel hors Maroc | Convention banque-prestataire, protocole de caviardage, notice/consentement ou autre base légale, registre des accès, analyse de risques, destruction |
| 2. Orientation réglementaire Bank Al-Maghrib puis partenariat bancaire | Élevé pour sécuriser le périmètre et identifier le bon interlocuteur | Effort moyen ; réunion annoncée sous 2 jours pour les questions réglementaires ; présentation du projet sous 2 semaines, puis retour écrit sous 2 semaines ; cela ne garantit pas les échantillons [23] | Confusion entre accompagnement réglementaire et autorisation de traiter ; agrément éventuellement nécessaire | Note de projet, flux de données, typologie documentaire, mesures de protection, questions ciblées ; dossier d’agrément si applicable |
| 3. Dossier CNDP pour traitement de test au Maroc | Indispensable dès que le test utilise des données personnelles non anonymes | Effort élevé ; récépissé de déclaration annoncé sous 24 h si le dossier est complet ; avis d’autorisation annoncé sous 2 mois, prorogeable [21] [22] | Changement de finalité, numéro d’identité, interconnexion, sous-traitance, hébergement ou transfert à l’étranger | F211/F214 ou F112/F113, habilitation du signataire, information des personnes, consentement si nécessaire, contrat de sous-traitance, sécurité, durée, procédure d’effacement |
| 4. Échantillons ANCFCC contrôlés ou spécimens non individualisés | Élevé pour documents immobiliers et hypothèques ; nul pour relevés | Effort moyen à élevé ; délai **non documenté** | Accès aux livres fonciers réservé au titulaire ou mandataire ; risque de diffuser une propriété réelle | Demande de spécimens, lettre de finalité, liste de champs, convention de réutilisation, validation du caviardage |
| 5. Partenariat CNONM/notaires | Élevé pour actes authentiques, procurations, ventes, hypothèques et attestations notariales | Effort moyen ; délai **non documenté** | Secret professionnel, signatures, sceaux, identifiants et pièces annexes | Convention avec le CNONM ou un office, protocole de caviardage, règles sur sceaux/signatures, accès sur site, destruction |
| 6. Partenariat avec banques européennes ou employeurs de clients MRE | Élevé pour bulletins de salaire, avis d’imposition, attestations et relevés étrangers | Effort élevé ; délai **non documenté** | RGPD, secret bancaire, transferts internationaux, ré-identification et divergence des bases légales nationales | Accord de responsable/sous-traitant, analyse d’impact si nécessaire, protocole d’anonymisation, clauses de transfert, notice, journalisation, effacement |
| 7. Documents officiels publics réellement publiés mais hors banque | Moyen pour rapports financiers d’organisations, décisions et documents administratifs | Effort faible à moyen ; accès public documenté ; délai d’obtention **non documenté** | Pseudonymisation et licences de réutilisation ; absence de pièces annexes ; personnes physiques éventuellement citées | Registre de provenance, contrôle de licence, filtre des personnes physiques, justification de pertinence, retrait rapide en cas de réidentification |
| 8. Benchmarks publics R/RA à licence compatible, en complément seulement | Élevé pour OCR, mise en page et tableaux ; faible pour réalisme bancaire marocain | Effort faible pour la revue des fiches ; accès parfois restreint ; délais non documentés | NC/accès recherche, droits d’images, données personnelles, licences héritées | Registre des licences, validation de chaque composant, séparation des corpus de recherche et commerciaux, contrôle de provenance |

**Ordre recommandé :** commencer par une banque marocaine volontaire et un pilote CNDP cadré ; solliciter en parallèle ANCFCC et CNONM pour les pièces immobilières et notariales ; demander à Bank Al-Maghrib une orientation réglementaire ; compléter seulement ensuite avec quelques benchmarks publics dont la licence et la provenance sont documentées.

## Sources EXCLUES et pourquoi

- **Corpus public de relevés bancaires/factures/reçus de 150 000 images** : exclu de la qualification R/RA/S/M car sa propre fiche dit que la provenance peut être synthétique, publique, manuellement créée ou autorisée, sans dire quelle origine s’applique à chaque document ; la licence est « à préciser par le mainteneur ». [14]
- **DocVQA** : réel, mais téléchargement soumis à connexion au portail RRC et à des conditions d’accès ; licence commerciale non établie. [4]
- **RVL-CDIP/IIT-CDIP** : réel, mais licence du sous-ensemble non explicite sur la page et provenance d’archives pouvant contenir des identifiants ; aucune conclusion commerciale sûre. [3]
- **FUNSD et XFUND** : réels mais respectivement limités au non-commercial et sous CC BY-NC-SA 4.0. [1] [2]
- **DocILE** : mélange explicite de documents annotés et synthétiques, accès par formulaire pour la recherche ; il ne peut pas être traité comme un lot homogène de documents réels commercialement réutilisables. [11]
- **NIST SFRS** : exclu de R malgré son apparence de formulaires remplis, car la page officielle précise que les images sont synthétisées par ordinateur. [12]
- **Corpus de spécimens ou fiches de plateforme sans provenance et licence vérifiables** : à conserver au mieux comme pistes de modèles ou de documents synthétiques, jamais comme documents réels autorisés.
- **Documents réels trouvés sur des pages ouvertes sans base légale, sans licence ou avec données personnelles non caviardées** : exclus ; aucun nom, numéro, adresse ou autre donnée individuelle n’est reproduit dans ce rapport.

## Références

[1]: https://guillaumejaume.github.io/FUNSD/ "FUNSD – présentation du corpus"

[2]: https://github.com/doc-analysis/XFUND "XFUND – dépôt et licence du benchmark multilingue"

[3]: https://adamharley.com/rvl-cdip/ "RVL-CDIP – volume, classes et provenance"

[4]: https://www.docvqa.org/datasets "DocVQA – sources des documents et conditions d’accès"

[5]: https://github.com/applicaai/kleister-charity "Kleister Charity – dépôt et statistiques de répartition"

[6]: https://ar5iv.labs.arxiv.org/html/2105.05796 "Kleister – publication et description des documents financiers"

[7]: https://github.com/clovaai/cord "CORD – reçus indonésiens, volume et CC BY 4.0"

[8]: https://huggingface.co/datasets/bsmock/FinTabNet.c "FinTabNet.c – fiche et licence CDLA-Permissive-2.0"

[9]: https://cdla.dev/permissive-2-0/ "Community Data License Agreement – Permissive 2.0"

[10]: https://rrc.cvc.uab.es/?ch=13 "SROIE – page officielle de la compétition et caviardage"

[11]: https://docile.rossum.ai/ "DocILE – composition, accès recherche et documents synthétiques"

[12]: https://www.nist.gov/srd/nist-special-database-2 "NIST Special Database 2 – formulaires fiscaux synthétisés"

[13]: https://huggingface.co/datasets/sinabis-group/sinabis-1k-synthetic-pdf "Sinabis 1K Synthetic PDF – fiche, langues, volume et licence"

[14]: https://huggingface.co/datasets/devpatel18042004/receipts-invoices-bank-statements "Receipts, Invoices & Bank Statements – provenance et licence à préciser"

[15]: https://www.ancfcc.gov.ma/produits-et-formalit%C3%A9s/produits/ "ANCFCC – produits, duplicata et certificats"

[16]: https://www.ancfcc.gov.ma/ProcedureNormale/ "ANCFCC – procédure ordinaire d’immatriculation foncière"

[17]: https://www.courdecassation.fr/acces-rapide-judilibre/donnees-ouvertes-open-data-et-api "Cour de cassation – Judilibre, open data et pseudonymisation"

[18]: https://www.cnil.fr/fr/technologies/lanonymisation-de-donnees-personnelles "CNIL – anonymisation des données personnelles"

[19]: https://www.gov.uk/find-charity-information "GOV.UK – registre public des associations caritatives"

[20]: https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download "Charity Commission – extraits publics et Open Government Licence v3.0"

[21]: https://www.cndp.ma/notifier-un-traitement/ "CNDP – déclaration, autorisation et transfert à l’étranger"

[22]: https://www.cndp.ma/notifier-une-demande-dautorisation-prealable/ "CNDP – autorisation préalable et pièces à joindre"

[23]: https://www.bkam.ma/content/download/837309/9094002/version/1/file/Guide+des+fintechs+V2.pdf "Bank Al-Maghrib – Guide du parcours fintech"

[24]: https://www.bkam.ma/Communiques/Communique/2023/Sous-l-impulsion-de-bank-al-maghrib-lancement-par-le-groupement-professionnel-des-banques-du-maroc-gpbm "Bank Al-Maghrib – communiqué sur le GPBM"

[25]: https://notaires.org.ma/ "Conseil National de l’Ordre des Notaires du Maroc – site institutionnel"

[26]: https://notaires.org.ma/contacter-nous/ "CNONM – coordonnées et prise de contact"

[27]: https://www.cnil.fr/fr/recherche-scientifique-hors-sante-enjeux-et-avantages-de-lanonymisation-et-de-la-pseudonymisation "CNIL – anonymisation et pseudonymisation en recherche"

[28]: https://www.edpb.europa.eu/topics/ai-and-technology/anonymisation-pseudonymisation_en "CEPD – distinction anonymisation/pseudonymisation"

[29]: https://www.cnil.fr/fr/bac-a-sable-2021 "CNIL – dispositif d’accompagnement bac à sable"
