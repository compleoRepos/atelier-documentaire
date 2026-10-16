# Qualité documentaire et traduction — Prompt 1

## Résultats qualifiants et non qualifiants

| Dimension | Preuve réelle | Statut |
|---|---|---|
| Intégrité des originaux | SHA fichier avant/après, copies distinctes, test TIFF pixels/frame | testée techniquement ; aucune preuve d’authenticité |
| OCR preprocessing | Tesseract local sur corpus et dégradations, confidence/blocs/caractères/version/langues | mesuré ; **proxy de confiance**, pas exactitude |
| CER/WER corpus | aucune transcription humaine approuvée disponible | **null / non évalué** |
| Noms/dates/nombres/références OCR | pas de vérité terrain réelle ; invariants textuels des placeholders testés | OCR réel non validé ; invariants techniques testés |
| Traduction professionnelle arabe/français/anglais/espagnol/autres | adaptateur Qwen privé câblé, tests de payload/contexte/glossaire avec doubles | **pas d’inférence Qwen réelle**, qualité non évaluée |
| Fidelity/coherence/terminology/context/style | rubrique humaine existante ; aucun reviewer/Golden attendu approuvé fourni | **null / non validé** |
| Qwen contexte 32768 | budget complet, hash assets et comptes rendus testés avec tokenizer double | garde-fous testés, tokenizer réel absent |
| PDF/DOCX mise en page, runs et tableaux | renderer/mesures existants, tests techniques ; fidélité renforcée par Prompt 2 | reconstruction technique exécutée ; finale à intégrer et qualifier |
| Signature/cachet/photo/logo/QR | candidats conservateurs, non authentifiés ; restauration des zones candidates ; source conservée | protection candidate testée ; exhaustivité/authenticité non validées |
| Golden | 8 originaux potentiels ; aucun Expected humain | traitement technique, **pas de PASS Golden linguistique** |

## Preprocessing et conservation

Le pipeline garde l’original exact et réalise ses transformations sur des copies. Il mesure OCR avant/après, traite une confiance indisponible comme `null`, choisit l’original si un candidat baisse ou réduit trop le contenu OCR, et trace ses matrices inverses. Cropping : seuls les pixels réellement blancs en bordure peuvent être supprimés ; les marques très pâles et protections comptent comme contenu. La correction perspective conserve le canvas source complet autour du quadrilatère redressé. Une correction ambiguë ou excessive est refusée, jamais imposée pour améliorer artificiellement un score.

Les zones couleur et certains composants graphiques noirs produisent des `protected_visual_region` **candidates**. Elles ne constituent ni une reconnaissance de signataire, ni une validation de cachet, ni un inventaire exhaustif. La copie de traitement restaure les pixels de ces zones ; le renderer doit continuer d’utiliser l’original et les bbox source. Toute revue réelle doit compléter les zones manquées.

Le score `PreprocessingQualityScore` vaut `metric:ocr_confidence_proxy`, `validated:false`, `cer:null`, `wer:null`. Une hausse peut accompagner une erreur de lecture ; aucune confiance 0,99 n’est présentée comme 99 % de caractères exacts. Les mesures définitives par document et dégradation sont dans IMAGE-PREPROCESSING-REPORT.

## Traduction, mémoire et contexte

- JSON strict, IDs exacts, refus de clés dupliquées, IDs absents/en trop, `finish_reason=length` ou inconnu.
- Réserve sortie et marge incluses ; plafond constructeur 32768 ; vrai tokenizer local obligatoire pour inférence privée. Hash des assets et comptes de la requête enregistrés dans la provenance.
- Unités sémantiques atomiques pages/blocs/tableaux conservées ; un tableau trop grand devient overflow, pas un découpage arbitraire ni un texte inventé.
- Contexte minimal : type/domaine/langue, mémoire documentaire, terminologie, décisions précédentes, style/pays explicitement fournis. Les contextes accessoires peuvent être réduits, pas les blocs source atomiques.
- Cinq glossaires métier versionnés (RH, banque, juridique, finance, administration) : suggestions contextualisées en français, override client prioritaire. Ils ne sont pas des traductions humaines attendues et n’entrent pas dans Golden.
- Listes de mémoire : seuls `validated:true` sont repris. Les mappings internes legacy restent des projections trusted pour compatibilité ; les API DB existantes filtrent les mémoires validées par tenant.
- Français détecté : conservé sans inférence. Échec privé : original conservé avec issue critique, **pas de fallback public ou substitution offline cachée**.
- Entités textuelles connues : placeholders puis restauration exacte, blocage si altérées. Ceci ne remplace pas une transcription OCR humaine des identifiants réels.

## Verdict de qualification

**Ne pas déclarer `VALIDATED`, `BANK-READY` ou « zéro hallucination » au sens documentaire universel.** Les invariants testés sont précis et limités aux assertions exercées. Manquent : endpoint/tokenizer Qwen réels, poids OCR/embedding privés si nécessaires, transcriptions/traductions attendues humaines, rubriques et baseline, recette sur infrastructure bancaire et revue exhaustive des visuels. Après le merge Prompt 2, relancer tout le corpus privé et les tests de rendu/qualité avant promotion.

## Interim explicitement autorisé sur synthétique

Provider Interim/gpt-5-mini distinct de Qwen, live sur 3 blocs synthétiques anglais/arabe/espagnol→français uniquement. JSON/IDs, glossaire et entités/dates/références fictives passent ; ce ne sont pas des scores de qualité humaine. Compteur GPT réel plus framing/UTF8 upper, max_completion_tokens total8000, circuit/calibration et corpusSHA denylist. **Traduction des 8 réels NOT_EXECUTED par décision utilisateur**, Qwen privé toujours NOT_AVAILABLE_IN_ENVIRONMENT. Voir INTERIM-TRANSITION.md pour contrat officiel, sondes et limites de la preuve observée.
