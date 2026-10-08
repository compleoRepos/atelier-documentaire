"""Versioned terminology seeds for professional French prompts, not Golden truths.

Seeds are contextual suggestions. They never validate full-document translation or
enter the offline human translation memory. Explicit client terminology wins.
"""
from __future__ import annotations

from collections.abc import Mapping

VERSION = "professional-fr-terminology-v1"
DOMAINS = {
    "HR": [("Employment Certificate", "Attestation de travail"),
           ("employment contract", "contrat de travail"),
           ("شهادة العمل", "attestation de travail"),
           ("certificado de trabajo", "attestation de travail")],
    "BANKING": [("bank statement", "relevé bancaire"),
                ("account holder", "titulaire du compte"),
                ("كشف حساب", "relevé de compte"),
                ("extracto bancario", "relevé bancaire")],
    "LEGAL": [("power of attorney", "procuration"),
              ("governing law", "droit applicable"),
              ("التوكيل", "procuration"),
              ("poder notarial", "procuration")],
    "FINANCE": [("balance sheet", "bilan"),
                ("income statement", "compte de résultat"),
                ("cash flow", "flux de trésorerie"),
                ("estado de resultados", "compte de résultat")],
    "ADMINISTRATION": [("proof of residence", "justificatif de domicile"),
                       ("certified copy", "copie certifiée conforme"),
                       ("شهادة الإقامة", "certificat de résidence"),
                       ("certificado de residencia", "certificat de résidence")],
}
ALIASES = {"RH":"HR", "BANQUE":"BANKING", "JURIDIQUE":"LEGAL", "ADMIN":"ADMINISTRATION"}


def canonical_domain(value):
    domain = str(value or "").upper()
    return ALIASES.get(domain, domain)


def context_terms(domain, client_entries=None):
    domain = canonical_domain(domain)
    seeds = [{"source":source,"target":target,"domain":domain,"version":VERSION,
              "provenance":"curated_terminology_seed_not_human_reference"}
             for source,target in DOMAINS.get(domain,[])]
    if isinstance(client_entries,Mapping):
        client_entries = [{"source":k,"target":v} for k,v in client_entries.items()]
    clients = [dict(x) for x in client_entries or [] if isinstance(x,Mapping)
               and x.get("source") is not None and x.get("target") is not None
               and (not x.get("domain") or canonical_domain(x["domain"])==domain)]
    # Ordered mappings deterministically retain the client override, not seed duplicates.
    merged = {x["source"]:x for x in seeds}
    for entry in clients:
        entry["domain"] = domain
        merged[entry["source"]] = entry
    return list(merged.values())
