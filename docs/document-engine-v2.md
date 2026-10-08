# Document engine V2

## Périmètre et garanties

Le moteur reste **local et déterministe** pour l’ingestion, l’OCR, la classification et la reconstruction. Il ne contacte aucun service public et ne télécharge pas de poids au démarrage. Une absence de référence, de modèle ou de validation humaine produit une preuve manquante et `REVIEW_REQUIRED`, jamais un score inventé.

Les signatures publiques suivantes restent compatibles : `analyze_document`, `translate_document`, `reconstruct_document` et `evaluate_document`.

## Représentation

L’IR contient les pages, blocs textuels, coordonnées, provenance (`native`, `ocr:tesseract-local` ou `ocr:paddle-local`), langue/script, confiance OCR, tables, références DOCX et avertissements. Une confiance OCR est un signal d’incertitude, pas une exactitude. Les segments numériques, codes et noms ne sont pas classés « non traduits » uniquement parce qu’ils restent identiques.

La classification combine script, indices linguistiques et lexiques de type multilingues; elle expose la marge, la couverture et les ambiguïtés. Elle ne reconnaît pas un document par son nom de fichier et ne remplace pas une validation métier.

## OCR local

Le backend par défaut est Tesseract local (`TesseractOCR`). Les langues demandées sont normalisées (`fr`→`fra`, etc.) et filtrées sur les modèles effectivement installés. Le script observé sert à réduire la sélection lorsqu’aucune langue n’est imposée. Les langues absentes génèrent `OCR_LANGUAGE_UNAVAILABLE`; aucune installation n’est tentée.

PaddleOCR est optionnel via `PaddleOCRLocal`. Il exige `assets={"det_model_dir": "/chemin/local/det", "rec_model_dir": "/chemin/local/rec"}` (et éventuellement `cls_model_dir`) et vérifie que ces répertoires existent avant d’importer/initialiser PaddleOCR. Le worker doit donc monter les poids dans l’image privée. Sans ces chemins, le constructeur lève `PaddleAssetsError`; aucun autodownload n’est autorisé. API utilisable :

```python
from app.ai.ocr.paddle_local import PaddleOCRLocal
ocr = PaddleOCRLocal(languages=["fra"], assets={
    "det_model_dir": "/opt/models/paddle/det",
    "rec_model_dir": "/opt/models/paddle/rec",
})
result = ocr.image_to_blocks(image)
```

## DOCX

L’analyse DOCX tente une conversion réelle par `/usr/bin/soffice` dans un profil temporaire isolé, avec timeout borné, sans macros ni extensions externes. Le PDF produit sert aux pages et previews réelles; l’original DOCX est copié séparément. En cas d’échec ou de timeout, l’analyse conserve une IR logique mais signale explicitement `DOCX_LIBREOFFICE_*` et `REVIEW_REQUIRED`.

La reconstruction modifie uniquement les nœuds `w:t`, conserve les runs, styles, images, relations, tableaux et cellules fusionnées, et traduit aussi les paragraphes d’en-têtes/pieds lorsqu’ils sont adressables. La pagination du candidat est re-mesurée par LibreOffice, non dessinée par une page synthétique. Les tableaux exposent lignes/colonnes/cellules/fusions pour comparaison structurelle.

## Rendu et qualité

Le rendu fournit les chemins source/candidat/diff des previews, les masques minimaux des blocs textuels effectivement remplacés, les régions protégées, les débordements et les structures de tableaux. La qualité est appelée par import paresseux au contrat `app.ai.quality.engine.evaluate_quality(ir, translations, render_result, reference, options)`. Si ce module est absent pendant le développement, le moteur ferme l’évaluation (`REVIEW_REQUIRED`) et conserve les preuves locales; il ne fabrique aucun score.

Les diff pixelaires bruts restent des artefacts de diagnostic, pas une similarité sémantique. Les zones textuelles remplacées sont explicitement masquées; une page entière ne peut pas être masquée. Les images, signatures et cachets sont conservés visuellement quand possible, sans affirmer leur authenticité.

## Limites à traiter par le coordinateur

- Installer/mirrorer les poids PaddleOCR et effectuer la recette sur GPU privé.
- Fournir des références OCR/traduction humainement validées et versionnées; les huit originaux seuls ne sont pas une référence.
- Brancher l’implémentation complète du contrat qualité et les rapports Golden/CI sans modifier ce lot.
- Mesurer les performances et les résultats des huit originaux séparément des tests synthétiques.
