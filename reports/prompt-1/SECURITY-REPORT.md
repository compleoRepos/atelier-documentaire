# Sécurité et confidentialité — Prompt 1

## Périmètre réellement utilisé

Dépôt **privé explicitement autorisé**, branche exclusive Prompt 1, worktree et dépendances propres au sandbox de cette tâche. Original et archive privés récupérés uniquement depuis la tâche référencée autorisée. Les 8 originaux, textes OCR, images de traitement et previews ne sont pas versionnés. Les rapports publics omettent noms originaux, empreintes des documents réels, extraits, informations de personnes et liens privés de téléchargement.

**Aucun contenu/donnée des 8 PDF n’a été envoyé à un modèle externe. Après autorisation explicite, des appels Interim ont porté seulement sur des fixtures synthétiques non personnelles.** OCR = Tesseract installé localement ; OpenCV/Pillow/PyMuPDF/LibreOffice = traitements locaux. Les variables OpenAI préconfigurées servent exclusivement au mode Interim synthétique explicite, côté serveur ; pas au mode private ou offline. Elles ne sont ni affichées ni committées. Les accès GitHub et installation/audit de dépendances transmettent du code technique ou des noms/version de packages, pas les documents. Ce sandbox Interim est autorisé pour cette tâche mais n’est pas, à lui seul, une attestation du cloud privé bancaire de production.

## Contrôles et renforcements

| Contrôle | Mise en œuvre / preuve | Limite explicite |
|---|---|---|
| Original immuable | SHA avant/après, copie processing, rejet d’un output égal à l’original | SHA prouve l’intégrité, pas l’authenticité |
| Limites upload | extension/MIME/magic, structure PDF/DOCX, pages et pixels ; TIFF multipage contrôlé frame par frame | formats exotiques non ajoutés |
| Allocations images | taille source, rendu PDF et warps bornés avant allocation ; sortie perspective complète | CPU/temps varient selon page ; charge bancaire non benchmarkée |
| OCR | assets locaux, Tesseract timeout, orientation fail-safe, candidats rejetés si baisse/perte | OCR réel sans GT ne garantit pas exactitude |
| Endpoint privé | allowlist exacte, résolution non publique, redirects refusés, `trust_env=False` | DNS est revérifié mais pas une preuve complète anti-rebinding ; politiques réseau requises |
| SSRF metadata | link-local, multicast, unspecified, DNS public et URLs ambiguës refusés | allowlist/résolveur doivent rester administrés |
| Qwen fail-closed | vrai tokenizer local requis, plafond 32768, comptes/hash, sortie strict IDs/JSON, refus length/finish inconnu | modèle/tokenizer réels non provisionnés |
| Fallback | pas d’OpenAI public ; après exception privée, source conservée avec alerte critique, pas de substitution offline | offline explicitement demandé = mémoire/glossaire, pas inférence |
| Prompt injection | instructions système fixes, document non fiable dans JSON user ; placeholders restaurés | aucune revendication de résistance modèle absolue sans Qwen réel |
| Mémoires/glossaires | DB et récupération tenant-scopées, seules listes `validated:true` réutilisées, priorité client | mappings internes legacy = projections trusted du caller, pas attestations humaines nouvelles |
| Preview enhanced | authentification, tenant, version obligatoire si fournie, pas de fallback vers autre snapshot | access control technique, pas signature électronique |
| Cachets/signatures | candidats non authentifiés, pixels restaurés sur processing copy, renderer sur original | détection non exhaustive ; reviewer doit compléter |
| Journalisation | profil/version/opérations/SHA technique ; hash/comptes token dans provenance, pas corps documentaire dans audit | IR privé contient nécessairement le texte OCR et reste protégé par tenant |
| Final/revue/Golden | revue obligatoire, gate critiques et attestations existantes conservés | aucune approbation bancaire n’a été soumise ici |
| Dépendances | `npm audit --audit-level=high`, `pip-audit --strict`, résultats dans TEST-REPORT | absence de CVE connue au scan ≠ absence de vulnérabilité |

## Tests et éléments non exécutés

Les tests sécurité existants (MIME, fichiers invalides, zip-slip/archives, injection, tenant, rôles, revue et gates) sont inclus dans la suite technique finale. S’y ajoutent les tests SSRF metadata, allocations avant warp, frames TIFF, SHA, absence de fallback et isolation des previews enhanced.

La CI technique configure PostgreSQL/migrations, checks frontend, audits, Compose/Helm et builds Docker. Son résultat effectivement observé est dans TEST-REPORT, sans extrapolation. Le sandbox ne dispose pas de Docker ni de ClamAV pour une recette privée réelle. Aucun runner bancaire, endpoint Qwen privé, secret d’inférence, tokenizer Qwen réel ou références Golden approuvées n’est disponible à cette exécution. Les gates privés et release protégés ne sont **pas activés** pour les contourner.

## Verdict

**Technique sécurisée et testée dans le périmètre décrit ; qualification bancaire non acquise.** Fournir les assets privés, network policies/KMS/AV, tenant et Golden humains, puis exécuter la recette privée et la revue de fidélité après merge Prompt 2. Aucune propriété de cloud bancaire, score humain, exactitude de nom/date ou authenticité de cachet n’est inventée.

## Mode Interim synthétique

SHA des8réels refusésavant réseau, marker synthétique + allowlist du payload IR/contextes, production/private interdite. Budget préalable o200k+borneframing≤22000 + max_completion_tokens TOTAL≤8000 + marge2768≤32768 ; contrat officiel vérifié et conformité proxy observée sur sondes synthétiques. Contrôle post-call/circuit ne remplace pas pré-call. Une sortie length/refusal/JSON/usage incohérent est rejetée ; références humaines non validées. Corps et données privées du corpus jamais utilisés pour ces sondes ; tests de corruption contexte, SHA et tenants inclus.
