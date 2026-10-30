# Maintenance : correction des audits de dépendances

> Branche `maintenance/audits-securite-20261030`, base `d8bb59a` (tête RUN29).
> Date : 2026-10-30. Toutes les valeurs proviennent d'exécutions réelles sur
> l'arbre de cette branche, sauf mention contraire.

## 0. Verdict

| Critère | Preuve | Résultat |
|---|---|---|
| `pip-audit -r backend/requirements.txt --strict` | avant : 39 avis, tous sur Pillow 12.3.0 ; après : aucun | **corrigé** (rc=0) |
| `npm audit --audit-level=high` | avant : 12 avis (6 élevés, 6 modérés) ; après : aucun | **corrigé** (rc=0) |
| Aucun changement de code | seuls `backend/requirements.txt`, `frontend/package.json` et `frontend/package-lock.json` changent | **atteint** |
| Rendu et OCR inchangés | golden des 8 originaux sous Pillow 12.3.0 puis 13.0.0 | **identique** (§3.2) |
| Suite backend | périmètre CI sous Pillow 13.0.0 | **873/873** |
| Frontend | `npm ci`, typecheck, tests, build | **30/30**, build identique en taille |

**Décision proposée : GO pour fusion de la maintenance, indépendamment du
LOT 1.** Le passage de Pillow à une version majeure n'a produit aucune
différence mesurable sur les 8 originaux ; cette preuve ne couvre que ce
corpus et ne remplace pas la relecture humaine des documents traduits.

## 1. Changements

| Fichier | Avant | Après | Motif |
|---|---|---|---|
| `backend/requirements.txt` | `pillow==12.3.0` | `pillow==13.0.0` | les 39 avis portent sur 12.3.0 ; aucune version 12.x corrigée n'existe, 13.0.0 est la seule version corrective |
| `frontend/package.json` | `@angular/build` et `@angular/cli` 21.2.26, `vitest` 4.1.11 | 21.2.29 et 4.1.12 | correctifs de dépendances de construction et de test |
| `frontend/package-lock.json` | — | +206 / −261 lignes | dépendances transitives corrigées (`npm audit fix`) |

Aucun fichier Python, TypeScript, de configuration ou de CI n'est modifié.
Les trois paquets directs modifiés sont des `devDependencies` ; la section
`dependencies` de `package.json` est inchangée. Dans le lock, 85 entrées
changent (1 ajoutée, aucune retirée) : 77 sont des dépendances de
développement ; les 8 autres (`@angular/core`, `@angular/common`,
`@angular/compiler`, `@angular/animations`, `@angular/platform-browser`,
`rxjs`, `zone.js`, `tslib`) gardent exactement la même version et ne reçoivent
que la métadonnée `peer: true`. Le code livré au navigateur ne change donc pas.

## 2. Audits

| Audit | Avant (base `d8bb59a`) | Après (cette branche) |
|---|---|---|
| `pip-audit -r backend/requirements.txt --strict` | rc=1, 39 avis, paquet unique : Pillow 12.3.0 | rc=0, « No known vulnerabilities found » |
| `npm audit --audit-level=high` | rc=1, 12 avis (6 élevés, 6 modérés) : `@angular/build`, `@angular/cli`, `vitest` et dépendances transitives | rc=0, « found 0 vulnerabilities » |

## 3. Contrôles d'impact

### 3.1 Compatibilité de l'API Pillow

Les noms Pillow utilisés par le code (1 module et 26 symboles, relevés
statiquement dans `backend/app` et `tools`) ont été importés et résolus un par
un : **27/27 résolus sous 12.3.0 et 27/27 sous 13.0.0**, aucun nom manquant.

### 3.2 Golden des 8 originaux (rendu et OCR)

Même code (`d8bb59a`), même machine, même commande
(`pytest backend/tests/golden_dataset`), moteur offline ; seule la version de
Pillow change.

| Mesure | Pillow 12.3.0 contre 13.0.0 |
|---|---|
| tests golden | 8/8 réussis dans les deux cas |
| images PNG produites | 449/449 identiques au pixel près |
| pages du PDF candidat | 31/31, 0 pixel différent |
| blocs OCR | 1 338/1 338 inchangés (texte et confiance) |
| champs JSON différents | 318, tous des chemins de fichiers qui ne diffèrent que par le nom du répertoire temporaire d'exécution |

Les originaux et les sorties restent locaux et ne sont pas versionnés.

### 3.3 Backend

| Exécution | Résultat |
|---|---|
| `ruff check backend tools` | 0 erreur |
| `pytest backend/tests/unit backend/tests/integration backend/tests/e2e backend/tests/regression backend/tests/security` sous Pillow 13.0.0 | **873 réussis**, 0 échec, 236 s |

### 3.4 Frontend

| Exécution | Base | Cette branche |
|---|---|---|
| `npm ci` | réussi | réussi |
| `npm run typecheck` | réussi | réussi |
| `npm test` | 30/30 (8 fichiers) | **30/30** (8 fichiers) |
| `npm run build`, total initial | 435,07 kB (114,32 kB transférés) | 435,07 kB (114,32 kB transférés) |

## 4. Limites

* Pillow 13.0.0 est une version majeure : l'absence d'écart est prouvée sur les
  8 originaux, la suite technique et les noms d'API utilisés, pas sur tout
  document possible.
* Les avis npm portaient sur des outils de construction et de test, non sur le
  code livré au navigateur ; leur correction ne change pas le bundle.
* La CI GitHub de cette branche confirme ou infirme ces résultats ; elle est
  consignée dans la PR.
