"""Taxonomie des domaines métier des référentiels terminologiques (LOT 2).

Dix domaines. Six sont exactement ceux que produit la classification
documentaire existante (``app.domain.classification``) : HR, LEGAL, BANKING,
FINANCE, ADMINISTRATION, ACADEMIC. Quatre sont plus fins et rattachés à l'un
d'eux : PAYROLL (paie) à HR, NOTARIAL (actes notariés) à LEGAL, TAX
(fiscalité) et INSURANCE (assurance) à FINANCE.

Compatibilité entrée / document (``compatible``) :
* même domaine ;
* même famille parent-enfant, dans les deux sens : une entrée PAYROLL vaut pour
  un document classé HR (la classification ne descend pas au niveau PAYROLL),
  une entrée HR vaut pour un document déclaré PAYROLL ;
* deux domaines frères (TAX et INSURANCE) ne sont pas compatibles ;
* ``GENERAL`` (ou domaine vide) désigne une entrée transversale.

Cette taxonomie est une proposition soumise au métier ; elle n'est pas validée.
"""

from __future__ import annotations

DOMAINS: dict[str, str] = {
    "HR": "Ressources humaines et emploi",
    "PAYROLL": "Paie",
    "LEGAL": "Juridique et contrats",
    "NOTARIAL": "Actes notariés",
    "BANKING": "Banque",
    "FINANCE": "Finance et comptabilité",
    "TAX": "Fiscalité",
    "INSURANCE": "Assurance",
    "ADMINISTRATION": "Administration et démarches",
    "ACADEMIC": "Enseignement et diplômes",
}
PARENTS: dict[str, str] = {
    "PAYROLL": "HR",
    "NOTARIAL": "LEGAL",
    "TAX": "FINANCE",
    "INSURANCE": "FINANCE",
}
CLASSIFIER_DOMAINS = frozenset({"HR", "LEGAL", "BANKING", "FINANCE", "ADMINISTRATION", "ACADEMIC"})
GENERAL = "GENERAL"
_ALIASES = {
    "RH": "HR",
    "EMPLOI": "HR",
    "TRAVAIL": "HR",
    "EMPLOYMENT": "HR",
    "PAIE": "PAYROLL",
    "NOMINA": "PAYROLL",
    "NÓMINA": "PAYROLL",
    "LOHN": "PAYROLL",
    "LOHNABRECHNUNG": "PAYROLL",
    "BANQUE": "BANKING",
    "BANCA": "BANKING",
    "BANK": "BANKING",
    "JURIDIQUE": "LEGAL",
    "JURIDICO": "LEGAL",
    "JURÍDICO": "LEGAL",
    "RECHT": "LEGAL",
    "NOTARIAT": "NOTARIAL",
    "NOTARIADO": "NOTARIAL",
    "ADMIN": "ADMINISTRATION",
    "ADMINISTRATIF": "ADMINISTRATION",
    "ADMINISTRATIVO": "ADMINISTRATION",
    "VERWALTUNG": "ADMINISTRATION",
    "FINANCES": "FINANCE",
    "FINANZAS": "FINANCE",
    "FINANZEN": "FINANCE",
    "COMPTABILITE": "FINANCE",
    "COMPTABILITÉ": "FINANCE",
    "FISCAL": "TAX",
    "FISCALITE": "TAX",
    "FISCALITÉ": "TAX",
    "FISCALIDAD": "TAX",
    "IMPOTS": "TAX",
    "IMPÔTS": "TAX",
    "STEUERN": "TAX",
    "ASSURANCE": "INSURANCE",
    "SEGUROS": "INSURANCE",
    "VERSICHERUNG": "INSURANCE",
    "ENSEIGNEMENT": "ACADEMIC",
    "EDUCATION": "ACADEMIC",
    "ÉDUCATION": "ACADEMIC",
    "EDUCACION": "ACADEMIC",
    "EDUCACIÓN": "ACADEMIC",
    "BILDUNG": "ACADEMIC",
    "GÉNÉRAL": GENERAL,
    "GENERIC": GENERAL,
}


def canonical_domain(value: object) -> str | None:
    """Code canonique, ``GENERAL`` si vide, ou None si la valeur est hors taxonomie."""
    code = str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    if not code:
        return GENERAL
    code = _ALIASES.get(code, code)
    if code == GENERAL or code in DOMAINS:
        return code
    return None


def family(code: str) -> str:
    return PARENTS.get(code, code)


def compatible(entry_domain: object, document_domain: object) -> bool | None:
    """True/False ; None si le domaine du document est inconnu ou hors taxonomie."""
    entry = canonical_domain(entry_domain)
    if entry == GENERAL:
        return True
    document = canonical_domain(document_domain)
    if document in (None, GENERAL):
        return None
    if entry is None:
        return False
    if entry == document:
        return True
    return PARENTS.get(entry) == document or PARENTS.get(document) == entry
