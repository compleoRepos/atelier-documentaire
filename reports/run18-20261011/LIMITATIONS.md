# RUN18 — Limitations connues

Toutes les limites ci-dessous restent visibles dans les sorties (statut et raison par bloc, codes
d'alerte, `REVIEW_REQUIRED`). Chiffres : verdict `run24`, empreinte du code `4d4956273c97d866`, mesure
`measure-v2.1-run18`, caractères source.

## 1. Validation

| Limite | Effet | Conséquence |
|---|---|---|
| Aucune référence humaine pour les 8 documents | aucune mesure de qualité de traduction (CER/WER/adéquation) n'est possible ; « écrit » signifie « la cible du moteur est lisible dans le PDF », pas « la traduction est juste » | 8 documents `REVIEW_REQUIRED` ; aucun PASS |
| Moteur temporaire Interim (gpt-5-mini), pas Qwen | les résultats ne qualifient pas le modèle privé cible ; aucun repli public automatique | qualification Qwen/vLLM à faire sur l'infrastructure privée |
| Jeu golden privé absent de la CI publique (présent seulement en local, hors Git) | en local : 8 passed, contrôle **technique** de bout en bout ; en CI, les portes `private acceptance` sont SKIPPED, ce qui n'est pas un PASS | voir `TEST_RESULTS.md` |
| Qualification bancaire | non validée | revue humaine obligatoire |

## 2. Moteur de traduction

* **Variance** : à source identique, deux passages Interim ont donné une cible différente pour 70,6 % des
  caractères. Le verdict utilise une mémoire de traduction à signature de contenu (F16) ; sans elle, un
  nouveau passage donnera d'autres chiffres.
* **Retours inchangés** : 2 456 caractères attendus ont été renvoyés en source malgré la reprise unique ;
  première cause de non-traduction (DOC-006 970, DOC-007 537, DOC-008 388, DOC-004 264).
* **Garde d'entités** : 420 caractères (DOC-002 206, DOC-007 159, DOC-006 55) restent en source parce que la
  sortie modifiait une entité protégée. Comportement voulu ; la baseline les traduisait sans ce contrôle.

## 3. Rendu et mise en page

* **Débordements** : le français est plus long que la source (≈ 2× pour des libellés arabes). Quand ni la
  croissance (F5), ni la réduction de police (plancher 72 %), ni un cadre plus large ne suffisent, la
  traduction est refusée et signalée : 1 068 caractères absents (DOC-004 455, DOC-007 354, DOC-008 193,
  DOC-006 66). Pas de recomposition de la mise en page.
* **Encre résiduelle** (garde D20) : quand le masque ne peut pas effacer toute l'encre source sous la
  traduction, celle-ci est refusée : 1 179 caractères (DOC-007 732, DOC-004 345, DOC-005 88, DOC-006 14).
* **Masques dangereux** : 315 caractères (DOC-002 133, DOC-004 111, DOC-008 35, DOC-007 32, DOC-006 4).
* **Écriture droite-à-gauche dans la cible** (F6 non implémenté) : 170 caractères refusés
  (`RTL_SHAPING_UNSUPPORTED` : DOC-001 93, DOC-004 47, DOC-006 30).
* **Écriture manuscrite** : un fragment OCR d'annotation manuscrite (confiance 0,21, DOC-002) est traduit
  et imprimé près de l'annotation. Calibration : 17 blocs appliqués ont une confiance OCR < 0,5, dont
  environ 5 lectures dégradées, mais aussi des titres en gras légitimes lus entre 0,23 et 0,29 ; aucun
  seuil ne les sépare. Non corrigé. Piste : détection de régions manuscrites à l'analyse.

## 4. Analyse et structure

* **Structure de formulaire ambiguë** (garde D16) : 744 caractères restent en source (DOC-006 367, DOC-007
  188, DOC-001 140, DOC-004 35, DOC-005 14). F2/F10/F13 en ont réduit le nombre sans lever la garde.
* **OCR non fiable** (F13b, F18) : 256 caractères volontairement non envoyés (DOC-004 154, DOC-006 71,
  DOC-007 19, DOC-008 7, DOC-005 5).
* **Cases à cocher** : pas de vérité terrain, rappel non mesuré ; les petits carrés pleins à mi-hauteur de
  ligne ne sont pas détectés. `PROTECTED_REGION_CHANGED` ×8 (DOC-004) reste à revoir.
* **Langue par bloc** (F4) : dépend des données lexicales wordfreq (licence CC-BY-SA-4.0, à valider avant
  distribution) ; en leur absence, aucune relabellisation.
* **F14** (lignes courtes à faible confiance dans une langue absente du document) : non implémenté en
  général ; seule la forme F18, limitée aux lignes d'option, est active.

## 5. Contrôles qualité

* **Faux positif d'unité** : l'extracteur d'unités (`app/ai/quality/engine.py`) reconnaît « metre(s) »
  mais pas la forme française accentuée « mètre(s) » ; une longueur correctement traduite (DOC-006) produit
  `HALLUCINATION_UNIT_CHANGED` (déjà présent en run17). Non corrigé dans run18 ; l'alerte reste visible.
  Correctif proposé : ajouter les formes accentuées et un test.
* **Date collée par l'OCR** (DOC-006) : classée comme code ; la traduction du mois déclenche deux alertes
  d'entité critique alors que la valeur est exacte. Alerte conservatrice conservée.
* **`UNMAPPED_TABLE_CONTENT`** (DOC-007) : cadres pleine page détectés sur deux versos blancs ; le service
  ne mesure pas l'encre de page et ne peut pas distinguer une page blanche d'un OCR en échec. Piste : mesure
  d'encre par page.

## 6. Mesure

* La mesure « écrit » est un rappel de mots de la cible dans les mots insérés près du bloc : elle ne juge ni
  l'ordre, ni le sens. 73 caractères sont « placés mais non retrouvés » (DOC-004 45, DOC-006 28).
* Une région visuelle est « altérée » au-delà de 2 % de pixels modifiés ; les régions « image » des scans
  sont souvent des bandes de lignes de texte, dont l'altération est le remplacement attendu du texte.
* La baseline ne signalait pas ses réductions/troncatures : ses débordements sont un minimum.
* Les écarts d'attendu entre runs viennent de la segmentation ; la règle de décision est identique.

## 7. Reproductibilité du verdict

Le verdict réutilise l'OCR du passage run18a (produit par le code OCR actuel) ; protections et
vérification de lignes sont réappliquées par le code courant à chaque passage, puis les traductions sont
servies par la mémoire F16 (0 requête). Rejouer avec Interim sans mémoire donnera des cibles différentes ;
le déterminisme d'un nouvel OCR complet (même version de Tesseract, `OMP_THREAD_LIMIT=1`) est attendu mais
n'a pas été re-vérifié pendant run18.
