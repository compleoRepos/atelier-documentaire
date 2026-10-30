"""Corpus synthétique DICE (RAG) LOT 2 : 8 catégories x 5 paires de langues.

Chaque document existe en gabarits parallèles FR/EN/AR/ES/DE : les termes
attendus, nombres, dates et identifiants sont connus par construction, et la
version parallèle dans la langue cible sert de *référence candidate
synthétique* (rédigée par l'outil, **non validée par un humain**) pour des
indicateurs automatiques de substitution (chrF). Aucune donnée réelle : noms,
sociétés, identifiants et montants sont fabriqués.

Sorties (hors dépôt) : ``docs/*.json`` ({ir, options}), ``expected/*.json``,
``referential.csv`` (import réel par l'API d'import), ``manifest.json``.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("fr", "en", "ar", "es", "de")
PAIRS = (("en", "fr"), ("ar", "fr"), ("es", "fr"), ("de", "fr"), ("fr", "en"))

# Termes : clé -> domaine, puis par langue (terme, synonymes, variantes).
TERMS: dict[str, dict] = {
    "employment_certificate": {
        "domain": "HR",
        "fr": ("attestation de travail", ["attestation d'emploi"], []),
        "en": ("employment certificate", ["certificate of employment"], []),
        "ar": ("شهادة عمل", [], []),
        "es": ("certificado de trabajo", ["certificado laboral"], []),
        "de": ("Arbeitsbescheinigung", ["Beschäftigungsnachweis"], []),
    },
    "employer": {
        "domain": "HR",
        "fr": ("employeur", [], []),
        "en": ("employer", [], []),
        "ar": ("صاحب العمل", ["المشغل"], []),
        "es": ("empleador", ["empresa empleadora"], []),
        "de": ("Arbeitgeber", [], []),
    },
    "employee": {
        "domain": "HR",
        "fr": ("salarié", [], []),
        "en": ("employee", [], []),
        "ar": ("أجير", [], []),
        "es": ("trabajador", [], []),
        "de": ("Arbeitnehmer", [], []),
    },
    "permanent_contract": {
        "domain": "HR",
        "fr": ("contrat à durée indéterminée", [], ["CDI"]),
        "en": ("permanent employment contract", ["open-ended contract"], []),
        "ar": ("عقد عمل غير محدد المدة", [], []),
        "es": ("contrato indefinido", [], []),
        "de": ("unbefristeter Arbeitsvertrag", [], []),
    },
    "job_title": {
        "domain": "HR",
        "fr": ("intitulé du poste", [], []),
        "en": ("job title", [], []),
        "ar": ("المسمى الوظيفي", [], []),
        "es": ("denominación del puesto", [], []),
        "de": ("Stellenbezeichnung", [], []),
    },
    "trial_period": {
        "domain": "HR",
        "fr": ("période d'essai", [], []),
        "en": ("probationary period", ["trial period"], []),
        "ar": ("فترة الاختبار", [], []),
        "es": ("período de prueba", [], ["periodo de prueba"]),
        "de": ("Probezeit", [], []),
    },
    "notice_period": {
        "domain": "HR",
        "fr": ("préavis", ["délai de préavis"], []),
        "en": ("notice period", [], []),
        "ar": ("مدة الإشعار", [], []),
        "es": ("plazo de preaviso", [], []),
        "de": ("Kündigungsfrist", [], []),
    },
    "paid_leave": {
        "domain": "HR",
        "fr": ("congés payés", [], []),
        "en": ("paid leave", ["paid holidays"], []),
        "ar": ("العطلة السنوية المؤدى عنها", [], []),
        "es": ("vacaciones retribuidas", [], []),
        "de": ("bezahlter Urlaub", [], []),
    },
    "resignation": {
        "domain": "HR",
        "fr": ("démission", [], []),
        "en": ("resignation", [], []),
        "ar": ("الاستقالة", [], []),
        "es": ("dimisión", [], []),
        "de": ("Eigenkündigung", [], []),
    },
    "pay_slip": {
        "domain": "PAYROLL",
        "fr": ("bulletin de paie", [], ["bulletin de salaire"]),
        "en": ("pay slip", [], ["payslip"]),
        "ar": ("ورقة الأجر", [], []),
        "es": ("nómina", ["recibo de salario"], []),
        "de": ("Gehaltsabrechnung", [], ["Lohnabrechnung"]),
    },
    "gross_salary": {
        "domain": "PAYROLL",
        "fr": ("salaire brut", [], []),
        "en": ("gross salary", ["gross pay"], []),
        "ar": ("الأجر الإجمالي", [], []),
        "es": ("salario bruto", [], []),
        "de": ("Bruttogehalt", [], []),
    },
    "net_salary": {
        "domain": "PAYROLL",
        "fr": ("salaire net", ["net à payer"], []),
        "en": ("net salary", ["net pay"], []),
        "ar": ("الأجر الصافي", [], []),
        "es": ("salario neto", ["líquido a percibir"], []),
        "de": ("Nettogehalt", ["Auszahlungsbetrag"], []),
    },
    "base_salary": {
        "domain": "PAYROLL",
        "fr": ("salaire de base", [], []),
        "en": ("base salary", [], []),
        "ar": ("الأجر الأساسي", [], []),
        "es": ("salario base", [], []),
        "de": ("Grundgehalt", [], []),
    },
    "social_contributions": {
        "domain": "PAYROLL",
        "fr": ("cotisations sociales", [], []),
        "en": ("social security contributions", [], []),
        "ar": ("الاشتراكات الاجتماعية", [], []),
        "es": ("cotizaciones a la seguridad social", [], []),
        "de": ("Sozialversicherungsbeiträge", [], []),
    },
    "income_tax": {
        "domain": "PAYROLL",
        "fr": ("prélèvement à la source", [], []),
        "en": ("income tax withholding", [], []),
        "ar": ("الضريبة على الدخل المقتطعة من المنبع", [], []),
        "es": ("retención del impuesto sobre la renta", [], []),
        "de": ("Lohnsteuerabzug", [], []),
    },
    "overtime": {
        "domain": "PAYROLL",
        "fr": ("heures supplémentaires", [], []),
        "en": ("overtime", [], []),
        "ar": ("الساعات الإضافية", [], []),
        "es": ("horas extraordinarias", [], []),
        "de": ("Überstunden", [], []),
    },
    "seniority_bonus": {
        "domain": "PAYROLL",
        "fr": ("prime d'ancienneté", [], []),
        "en": ("seniority bonus", [], []),
        "ar": ("منحة الأقدمية", [], []),
        "es": ("complemento de antigüedad", [], []),
        "de": ("Betriebszugehörigkeitszulage", [], []),
    },
    "bank_statement": {
        "domain": "BANKING",
        "fr": ("relevé de compte", [], ["relevé bancaire"]),
        "en": ("bank statement", ["account statement"], []),
        "ar": ("كشف الحساب", [], []),
        "es": ("extracto bancario", [], []),
        "de": ("Kontoauszug", [], []),
    },
    "account_holder": {
        "domain": "BANKING",
        "fr": ("titulaire du compte", [], []),
        "en": ("account holder", [], []),
        "ar": ("صاحب الحساب", [], []),
        "es": ("titular de la cuenta", [], []),
        "de": ("Kontoinhaber", [], []),
    },
    "transfer": {
        "domain": "BANKING",
        "fr": ("virement bancaire", [], []),
        "en": ("bank transfer", ["wire transfer"], []),
        "ar": ("تحويل بنكي", [], []),
        "es": ("transferencia bancaria", [], []),
        "de": ("Überweisung", [], []),
    },
    "direct_debit": {
        "domain": "BANKING",
        "fr": ("prélèvement automatique", [], []),
        "en": ("direct debit", [], []),
        "ar": ("الاقتطاع البنكي التلقائي", [], []),
        "es": ("domiciliación bancaria", [], []),
        "de": ("Lastschrift", [], []),
    },
    "closing_balance": {
        "domain": "BANKING",
        "fr": ("solde final", [], []),
        "en": ("closing balance", [], []),
        "ar": ("الرصيد النهائي", [], []),
        "es": ("saldo final", [], []),
        "de": ("Endsaldo", [], []),
    },
    "overdraft": {
        "domain": "BANKING",
        "fr": ("découvert autorisé", [], []),
        "en": ("authorised overdraft", [], []),
        "ar": ("السحب على المكشوف المرخص", [], []),
        "es": ("descubierto autorizado", [], []),
        "de": ("eingeräumte Überziehung", [], []),
    },
    "residence_certificate": {
        "domain": "ADMINISTRATION",
        "fr": ("certificat de résidence", [], []),
        "en": ("certificate of residence", [], []),
        "ar": ("شهادة السكنى", [], []),
        "es": ("certificado de residencia", [], []),
        "de": ("Meldebescheinigung", [], []),
    },
    "issuing_authority": {
        "domain": "ADMINISTRATION",
        "fr": ("autorité de délivrance", [], []),
        "en": ("issuing authority", [], []),
        "ar": ("السلطة المصدرة", [], []),
        "es": ("autoridad expedidora", [], []),
        "de": ("ausstellende Behörde", [], []),
    },
    "national_id": {
        "domain": "ADMINISTRATION",
        "fr": ("carte nationale d'identité", [], []),
        "en": ("national identity card", [], []),
        "ar": ("البطاقة الوطنية للتعريف", [], []),
        "es": ("documento nacional de identidad", [], []),
        "de": ("Personalausweis", [], []),
    },
    "marital_status": {
        "domain": "ADMINISTRATION",
        "fr": ("situation de famille", [], []),
        "en": ("marital status", [], []),
        "ar": ("الحالة العائلية", [], []),
        "es": ("estado civil", [], []),
        "de": ("Familienstand", [], []),
    },
    "power_of_attorney": {
        "domain": "NOTARIAL",
        "fr": ("procuration", [], []),
        "en": ("power of attorney", [], []),
        "ar": ("وكالة", [], []),
        "es": ("poder notarial", [], []),
        "de": ("Vollmacht", [], []),
    },
    "principal": {
        "domain": "LEGAL",
        "fr": ("mandant", [], []),
        "en": ("principal", [], []),
        "ar": ("الموكل", [], []),
        "es": ("poderdante", [], []),
        "de": ("Vollmachtgeber", [], []),
    },
    "agent": {
        "domain": "LEGAL",
        "fr": ("mandataire", [], []),
        "en": ("attorney-in-fact", ["agent"], []),
        "ar": ("الوكيل", [], []),
        "es": ("apoderado", [], []),
        "de": ("Bevollmächtigter", [], []),
    },
    "governing_law": {
        "domain": "LEGAL",
        "fr": ("droit applicable", [], []),
        "en": ("governing law", [], []),
        "ar": ("القانون الواجب التطبيق", [], []),
        "es": ("ley aplicable", [], []),
        "de": ("anwendbares Recht", [], []),
    },
    "competent_court": {
        "domain": "LEGAL",
        "fr": ("tribunal compétent", [], []),
        "en": ("competent court", [], []),
        "ar": ("المحكمة المختصة", [], []),
        "es": ("tribunal competente", [], []),
        "de": ("zuständiges Gericht", [], []),
    },
}

# Cas volontaires (dans le référentiel, pas dans TERMS) :
# * ambiguïté : deux cibles pour la même source et le même domaine -> jamais injecté ;
# * domaine frère : « cotisations » en ASSURANCE ne doit pas servir un document de PAIE.
AMBIGUOUS = {
    ("en", "fr"): ("deposit", ["dépôt", "caution"], "BANKING"),
    ("fr", "en"): ("dépôt", ["deposit", "filing"], "BANKING"),
}
SIBLING = {
    ("en", "fr"): ("contributions", "primes d'assurance"),
    ("ar", "fr"): ("الاشتراكات", "primes d'assurance"),
    ("es", "fr"): ("cotizaciones", "primes d'assurance"),
    ("de", "fr"): ("Beiträge", "primes d'assurance"),
    ("fr", "en"): ("cotisations", "insurance premiums"),
}
# Glossaire client (prioritaire sur le RAG, dans A comme dans C).
GLOSSARY_OVERRIDE = {"fr": "rémunération brute", "en": "gross remuneration"}

VALUES = {
    "COMPANY": {lang: "ALPHA DEMO SARL" for lang in LANGS},
    "PERSON": {**{lang: "Nour TEST" for lang in LANGS}, "ar": "نور تيست"},
    "PERSON2": {**{lang: "Lina EXEMPLE" for lang in LANGS}, "ar": "لينا إكزامبل"},
    "CITY": {**{lang: "Rabat" for lang in LANGS}, "ar": "الرباط"},
    "CUR": {lang: "EUR" for lang in LANGS},
    "JOB": {
        "fr": "analyste comptable",
        "en": "accounting analyst",
        "ar": "محلل محاسبي",
        "es": "analista contable",
        "de": "Buchhaltungsanalyst",
    },
}
AMOUNTS = {
    "AMOUNT1": 3250.00,
    "AMOUNT2": 162.50,
    "AMOUNT3": 418.75,
    "AMOUNT4": 3831.25,
    "AMOUNT5": 862.40,
    "AMOUNT6": 291.35,
    "AMOUNT7": 2677.50,
}
DATES = {
    "DATE1": (1, 9, 2021),
    "DATE2": (28, 2, 2022),
    "DATE3": (14, 3, 2026),
    "DATE4": (17, 3, 2026),
}
IDS = {"ID1": "ATT-2026-00187", "ID2": "REG-77-40219", "IBAN": "XX00 TEST 0000 0000 0042 1977"}
NUMS = {"N1": "18", "N2": "2", "N3": "12"}

# Gabarits parallèles : [[clé]] (terme principal), [[clé:syn]], [[clé:var]] ; {SLOT}.
TEMPLATES: dict[str, dict] = {
    "attestation": {
        "domain": "HR",
        "blocks": [
            {lang: "[[employment_certificate]]" for lang in LANGS},
            {
                "fr": "Je soussigné, directeur des ressources humaines de {COMPANY}, agissant pour l'[[employer]], certifie que {PERSON} est employé en qualité de [[employee]] depuis le {DATE1}.",
                "en": "I, the undersigned, human resources director of {COMPANY}, acting for the [[employer]], certify that {PERSON} has been working as an [[employee]] since {DATE1}.",
                "ar": "أنا الموقع أسفله، مدير الموارد البشرية بشركة {COMPANY}، نيابة عن [[employer]]، أشهد بأن {PERSON} يعمل بصفة [[employee]] منذ {DATE1}.",
                "es": "El abajo firmante, director de recursos humanos de {COMPANY}, en nombre del [[employer]], certifica que {PERSON} trabaja como [[employee]] desde el {DATE1}.",
                "de": "Der Unterzeichnende, Personalleiter von {COMPANY}, bescheinigt im Namen des [[employer]], dass {PERSON} seit dem {DATE1} als [[employee]] beschäftigt ist.",
            },
            {
                "fr": "L'intéressé est titulaire d'un [[permanent_contract]].",
                "en": "The person concerned holds a [[permanent_contract]].",
                "ar": "يتوفر المعني بالأمر على [[permanent_contract]].",
                "es": "La persona interesada es titular de un [[permanent_contract]].",
                "de": "Die betreffende Person hat einen [[permanent_contract]].",
            },
            {
                "fr": "[[job_title]] : {JOB}.",
                "en": "[[job_title]]: {JOB}.",
                "ar": "[[job_title]]: {JOB}.",
                "es": "[[job_title]]: {JOB}.",
                "de": "[[job_title]]: {JOB}.",
            },
            {
                "fr": "Sa [[trial_period]] s'est achevée le {DATE2}.",
                "en": "The [[trial_period]] ended on {DATE2}.",
                "ar": "انتهت [[trial_period]] بتاريخ {DATE2}.",
                "es": "Su [[trial_period]] finalizó el {DATE2}.",
                "de": "Die [[trial_period]] endete am {DATE2}.",
            },
            {
                "fr": "Son [[gross_salary]] mensuel s'élève à {AMOUNT1} {CUR}.",
                "en": "The monthly [[gross_salary]] amounts to {CUR} {AMOUNT1}.",
                "ar": "يبلغ [[gross_salary]] الشهري {AMOUNT1} {CUR}.",
                "es": "Su [[gross_salary]] mensual asciende a {AMOUNT1} {CUR}.",
                "de": "Das monatliche [[gross_salary]] beträgt {AMOUNT1} {CUR}.",
            },
            {
                "fr": "La présente attestation est délivrée pour servir et valoir ce que de droit. Référence : {ID1}.",
                "en": "This certificate is issued for all legal purposes. Reference: {ID1}.",
                "ar": "سلمت هذه الشهادة للإدلاء بها عند الحاجة. المرجع: {ID1}.",
                "es": "Se expide el presente certificado a los efectos oportunos. Referencia: {ID1}.",
                "de": "Diese Bescheinigung wird zur Vorlage bei Behörden ausgestellt. Referenz: {ID1}.",
            },
            {
                "fr": "Fait à {CITY}, le {DATE3}.",
                "en": "Done in {CITY} on {DATE3}.",
                "ar": "حرر في {CITY} بتاريخ {DATE3}.",
                "es": "En {CITY}, a {DATE3}.",
                "de": "{CITY}, den {DATE3}.",
            },
        ],
    },
    "contrat": {
        "domain": "HR",
        "blocks": [
            {lang: "[[permanent_contract]]" for lang in LANGS},
            {
                "fr": "Entre {COMPANY}, ci-après l'[[employer]], et {PERSON}, ci-après le [[employee]], il est convenu ce qui suit.",
                "en": "Between {COMPANY}, hereinafter the [[employer]], and {PERSON}, hereinafter the [[employee]], it is agreed as follows.",
                "ar": "بين {COMPANY}، المشار إليها بعده ب[[employer]]، و{PERSON}، المشار إليه بعده ب[[employee]]، تم الاتفاق على ما يلي.",
                "es": "Entre {COMPANY}, en adelante el [[employer]], y {PERSON}, en adelante el [[employee]], se acuerda lo siguiente.",
                "de": "Zwischen {COMPANY}, nachfolgend [[employer]], und {PERSON}, nachfolgend [[employee]], wird Folgendes vereinbart.",
            },
            {
                "fr": "Article 1 – Le [[employee]] est engagé en qualité de {JOB} à compter du {DATE1}, après une [[trial_period]] de {N1} semaines.",
                "en": "Article 1 – The [[employee]] is hired as {JOB} from {DATE1}, after a [[trial_period:syn]] of {N1} weeks.",
                "ar": "المادة 1 – يشغل [[employee]] منصب {JOB} ابتداء من {DATE1}، بعد [[trial_period]] مدتها {N1} أسبوعا.",
                "es": "Artículo 1 – El [[employee]] es contratado como {JOB} a partir del {DATE1}, tras un [[trial_period:var]] de {N1} semanas.",
                "de": "Artikel 1 – Der [[employee]] wird ab dem {DATE1} als {JOB} eingestellt, nach einer [[trial_period]] von {N1} Wochen.",
            },
            {
                "fr": "Article 2 – Le [[base_salary]] mensuel est fixé à {AMOUNT1} {CUR}, majoré des [[overtime]] effectuées.",
                "en": "Article 2 – The monthly [[base_salary]] is set at {CUR} {AMOUNT1}, plus any [[overtime]] worked.",
                "ar": "المادة 2 – حدد [[base_salary]] الشهري في {AMOUNT1} {CUR}، تضاف إليه [[overtime]] المنجزة.",
                "es": "Artículo 2 – El [[base_salary]] mensual se fija en {AMOUNT1} {CUR}, más las [[overtime]] realizadas.",
                "de": "Artikel 2 – Das monatliche [[base_salary]] beträgt {AMOUNT1} {CUR} zuzüglich geleisteter [[overtime]].",
            },
            {
                "fr": "Article 3 – Le [[employee]] bénéficie de {N1} jours ouvrables de [[paid_leave]] par an.",
                "en": "Article 3 – The [[employee]] is entitled to {N1} working days of [[paid_leave:syn]] per year.",
                "ar": "المادة 3 – يستفيد [[employee]] من {N1} يوم عمل من [[paid_leave]] في السنة.",
                "es": "Artículo 3 – El [[employee]] disfruta de {N1} días hábiles de [[paid_leave]] al año.",
                "de": "Artikel 3 – Der [[employee]] hat Anspruch auf {N1} Arbeitstage [[paid_leave]] pro Jahr.",
            },
            {
                "fr": "Article 4 – En cas de [[resignation]], le [[employee]] respecte un [[notice_period:syn]] de {N2} mois.",
                "en": "Article 4 – In the event of [[resignation]], the [[employee]] shall observe a [[notice_period]] of {N2} months.",
                "ar": "المادة 4 – في حالة [[resignation]]، يلتزم [[employee]] ب[[notice_period]] قدرها {N2} أشهر.",
                "es": "Artículo 4 – En caso de [[resignation]], el [[employee]] respetará un [[notice_period]] de {N2} meses.",
                "de": "Artikel 4 – Im Fall einer [[resignation]] hält der [[employee]] eine [[notice_period]] von {N2} Monaten ein.",
            },
            {
                "fr": "Fait à {CITY}, le {DATE3}, en deux exemplaires.",
                "en": "Done in {CITY} on {DATE3}, in two copies.",
                "ar": "حرر في {CITY} بتاريخ {DATE3}، في نظيرين.",
                "es": "En {CITY}, a {DATE3}, por duplicado.",
                "de": "{CITY}, den {DATE3}, in zweifacher Ausfertigung.",
            },
        ],
    },
    "paie": {
        "domain": "PAYROLL",
        "glossary": True,
        "blocks": [
            {
                "fr": "[[pay_slip]] – Période : mars 2026",
                "en": "[[pay_slip:var]] – Period: March 2026",
                "ar": "[[pay_slip]] – الفترة: مارس 2026",
                "es": "[[pay_slip]] – Periodo: marzo de 2026",
                "de": "[[pay_slip:var]] – Zeitraum: März 2026",
            },
            {
                "fr": "Salarié : {PERSON} – Matricule : {ID1}",
                "en": "Employee: {PERSON} – Staff number: {ID1}",
                "ar": "الأجير: {PERSON} – رقم التسجيل: {ID1}",
                "es": "Trabajador: {PERSON} – Número de empleado: {ID1}",
                "de": "Arbeitnehmer: {PERSON} – Personalnummer: {ID1}",
            },
            {
                "fr": "[[base_salary]] : {AMOUNT1} {CUR}",
                "en": "[[base_salary]]: {CUR} {AMOUNT1}",
                "ar": "[[base_salary]]: {AMOUNT1} {CUR}",
                "es": "[[base_salary]]: {AMOUNT1} {CUR}",
                "de": "[[base_salary]]: {AMOUNT1} {CUR}",
            },
            {
                "fr": "[[seniority_bonus]] : {AMOUNT2} {CUR} ; [[overtime]] : {N3} h, soit {AMOUNT3} {CUR}",
                "en": "[[seniority_bonus]]: {CUR} {AMOUNT2}; [[overtime]]: {N3} h, i.e. {CUR} {AMOUNT3}",
                "ar": "[[seniority_bonus]]: {AMOUNT2} {CUR}؛ [[overtime]]: {N3} ساعة، أي {AMOUNT3} {CUR}",
                "es": "[[seniority_bonus]]: {AMOUNT2} {CUR}; [[overtime]]: {N3} h, es decir {AMOUNT3} {CUR}",
                "de": "[[seniority_bonus]]: {AMOUNT2} {CUR}; [[overtime]]: {N3} Std., d. h. {AMOUNT3} {CUR}",
            },
            {
                "fr": "[[gross_salary]] : {AMOUNT4} {CUR}",
                "en": "[[gross_salary:syn]]: {CUR} {AMOUNT4}",
                "ar": "[[gross_salary]]: {AMOUNT4} {CUR}",
                "es": "[[gross_salary]]: {AMOUNT4} {CUR}",
                "de": "[[gross_salary]]: {AMOUNT4} {CUR}",
            },
            {
                "fr": "[[social_contributions]] : {AMOUNT5} {CUR} ; [[income_tax]] : {AMOUNT6} {CUR}",
                "en": "[[social_contributions]]: {CUR} {AMOUNT5}; [[income_tax]]: {CUR} {AMOUNT6}",
                "ar": "[[social_contributions]]: {AMOUNT5} {CUR}؛ [[income_tax]]: {AMOUNT6} {CUR}",
                "es": "[[social_contributions]]: {AMOUNT5} {CUR}; [[income_tax]]: {AMOUNT6} {CUR}",
                "de": "[[social_contributions]]: {AMOUNT5} {CUR}; [[income_tax]]: {AMOUNT6} {CUR}",
            },
            {
                "fr": "[[net_salary:syn]] : {AMOUNT7} {CUR}, versé le {DATE4}",
                "en": "[[net_salary:syn]]: {CUR} {AMOUNT7}, paid on {DATE4}",
                "ar": "[[net_salary]]: {AMOUNT7} {CUR}، مؤدى بتاريخ {DATE4}",
                "es": "[[net_salary:syn]]: {AMOUNT7} {CUR}, abonado el {DATE4}",
                "de": "[[net_salary:syn]]: {AMOUNT7} {CUR}, ausgezahlt am {DATE4}",
            },
        ],
    },
    "banque": {
        "domain": "BANKING",
        "blocks": [
            {
                "fr": "[[bank_statement:var]] n° {ID2}",
                "en": "[[bank_statement]] No. {ID2}",
                "ar": "[[bank_statement]] رقم {ID2}",
                "es": "[[bank_statement]] n.º {ID2}",
                "de": "[[bank_statement]] Nr. {ID2}",
            },
            {
                "fr": "[[account_holder]] : {PERSON} – IBAN : {IBAN}",
                "en": "[[account_holder]]: {PERSON} – IBAN: {IBAN}",
                "ar": "[[account_holder]]: {PERSON} – رقم الحساب الدولي: {IBAN}",
                "es": "[[account_holder]]: {PERSON} – IBAN: {IBAN}",
                "de": "[[account_holder]]: {PERSON} – IBAN: {IBAN}",
            },
            {
                "fr": "{DATE3} – [[transfer]] reçu de {COMPANY} : +{AMOUNT7} {CUR}",
                "en": "{DATE3} – [[transfer:syn]] received from {COMPANY}: +{CUR} {AMOUNT7}",
                "ar": "{DATE3} – [[transfer]] وارد من {COMPANY}: +{AMOUNT7} {CUR}",
                "es": "{DATE3} – [[transfer]] recibida de {COMPANY}: +{AMOUNT7} {CUR}",
                "de": "{DATE3} – [[transfer]] von {COMPANY} erhalten: +{AMOUNT7} {CUR}",
            },
            {
                "fr": "{DATE4} – [[direct_debit]] assurance habitation : -{AMOUNT2} {CUR}",
                "en": "{DATE4} – [[direct_debit]] home insurance: -{CUR} {AMOUNT2}",
                "ar": "{DATE4} – [[direct_debit]] تأمين السكن: -{AMOUNT2} {CUR}",
                "es": "{DATE4} – [[direct_debit]] seguro de hogar: -{AMOUNT2} {CUR}",
                "de": "{DATE4} – [[direct_debit]] Hausratversicherung: -{AMOUNT2} {CUR}",
            },
            {
                "fr": "{DATE4} – Dépôt d'espèces au guichet : +{AMOUNT3} {CUR}",
                "en": "{DATE4} – Cash deposit at the counter: +{CUR} {AMOUNT3}",
                "ar": "{DATE4} – إيداع نقدي بالشباك: +{AMOUNT3} {CUR}",
                "es": "{DATE4} – Ingreso en efectivo en ventanilla: +{AMOUNT3} {CUR}",
                "de": "{DATE4} – Bareinzahlung am Schalter: +{AMOUNT3} {CUR}",
            },
            {
                "fr": "[[closing_balance]] : {AMOUNT4} {CUR}. Aucun [[overdraft]] n'a été utilisé.",
                "en": "[[closing_balance]]: {CUR} {AMOUNT4}. No [[overdraft]] was used.",
                "ar": "[[closing_balance]]: {AMOUNT4} {CUR}. لم يتم استعمال أي [[overdraft]].",
                "es": "[[closing_balance]]: {AMOUNT4} {CUR}. No se ha utilizado ningún [[overdraft]].",
                "de": "[[closing_balance]]: {AMOUNT4} {CUR}. Es wurde keine [[overdraft]] in Anspruch genommen.",
            },
        ],
    },
    "administratif": {
        "domain": "ADMINISTRATION",
        "blocks": [
            {lang: "[[residence_certificate]]" for lang in LANGS},
            {
                "fr": "L'[[issuing_authority]] certifie que {PERSON}, titulaire de la [[national_id]] n° {ID1}, réside à {CITY}.",
                "en": "The [[issuing_authority]] certifies that {PERSON}, holder of [[national_id]] No. {ID1}, resides in {CITY}.",
                "ar": "تشهد [[issuing_authority]] بأن {PERSON}، حامل [[national_id]] رقم {ID1}، يقيم ب{CITY}.",
                "es": "La [[issuing_authority]] certifica que {PERSON}, titular del [[national_id]] n.º {ID1}, reside en {CITY}.",
                "de": "Die [[issuing_authority]] bescheinigt, dass {PERSON}, Inhaber des [[national_id]] Nr. {ID1}, in {CITY} wohnt.",
            },
            {
                "fr": "[[marital_status]] : célibataire.",
                "en": "[[marital_status]]: single.",
                "ar": "[[marital_status]]: عازب.",
                "es": "[[marital_status]]: soltero.",
                "de": "[[marital_status]]: ledig.",
            },
            {
                "fr": "Le présent certificat est délivré le {DATE3} et reste valable {N2} mois.",
                "en": "This certificate is issued on {DATE3} and remains valid for {N2} months.",
                "ar": "سلمت هذه الشهادة بتاريخ {DATE3} وتبقى صالحة لمدة {N2} أشهر.",
                "es": "El presente certificado se expide el {DATE3} y es válido durante {N2} meses.",
                "de": "Diese Bescheinigung wird am {DATE3} ausgestellt und ist {N2} Monate gültig.",
            },
            {
                "fr": "Numéro d'enregistrement : {ID2}.",
                "en": "Registration number: {ID2}.",
                "ar": "رقم التسجيل: {ID2}.",
                "es": "Número de registro: {ID2}.",
                "de": "Registriernummer: {ID2}.",
            },
            {
                "fr": "Signature et cachet de l'[[issuing_authority]].",
                "en": "Signature and stamp of the [[issuing_authority]].",
                "ar": "توقيع وخاتم [[issuing_authority]].",
                "es": "Firma y sello de la [[issuing_authority]].",
                "de": "Unterschrift und Stempel der [[issuing_authority]].",
            },
        ],
    },
    "juridique": {
        "domain": "LEGAL",
        "blocks": [
            {lang: "[[power_of_attorney]]" for lang in LANGS},
            {
                "fr": "Je soussigné, {PERSON}, ci-après le [[principal]], né le {DATE1},",
                "en": "I, the undersigned, {PERSON}, hereinafter the [[principal]], born on {DATE1},",
                "ar": "أنا الموقع أسفله، {PERSON}، المشار إليه بعده ب[[principal]]، المزداد بتاريخ {DATE1}،",
                "es": "El abajo firmante, {PERSON}, en adelante el [[principal]], nacido el {DATE1},",
                "de": "Der Unterzeichnende, {PERSON}, nachfolgend [[principal]], geboren am {DATE1},",
            },
            {
                "fr": "donne pouvoir à {PERSON2}, ci-après le [[agent]], de me représenter pour toute opération sur le compte n° {ID2}.",
                "en": "grants authority to {PERSON2}, hereinafter the [[agent:syn]], to represent me for any operation on account No. {ID2}.",
                "ar": "أوكل {PERSON2}، المشار إليها بعده ب[[agent]]، لتمثيلي في كل عملية على الحساب رقم {ID2}.",
                "es": "otorga poder a {PERSON2}, en adelante el [[agent]], para representarme en cualquier operación de la cuenta n.º {ID2}.",
                "de": "bevollmächtigt {PERSON2}, nachfolgend [[agent]], mich bei allen Vorgängen auf dem Konto Nr. {ID2} zu vertreten.",
            },
            {
                "fr": "La présente [[power_of_attorney]] est valable jusqu'au {DATE4} de l'année suivante.",
                "en": "This [[power_of_attorney]] is valid until {DATE4} of the following year.",
                "ar": "تبقى هذه [[power_of_attorney]] صالحة إلى غاية {DATE4} من السنة الموالية.",
                "es": "El presente [[power_of_attorney]] es válido hasta el {DATE4} del año siguiente.",
                "de": "Diese [[power_of_attorney]] gilt bis zum {DATE4} des Folgejahres.",
            },
            {
                "fr": "Le [[governing_law]] est le droit marocain ; tout litige relève du [[competent_court]] de {CITY}.",
                "en": "The [[governing_law]] is Moroccan law; any dispute falls under the [[competent_court]] of {CITY}.",
                "ar": "[[governing_law]] هو القانون المغربي، ويختص بكل نزاع [[competent_court]] ب{CITY}.",
                "es": "La [[governing_law]] es la ley marroquí; cualquier litigio corresponde al [[competent_court]] de {CITY}.",
                "de": "Das [[governing_law]] ist marokkanisches Recht; für Streitigkeiten ist das [[competent_court]] in {CITY} zuständig.",
            },
            {
                "fr": "Fait à {CITY}, le {DATE3}.",
                "en": "Done in {CITY} on {DATE3}.",
                "ar": "حرر في {CITY} بتاريخ {DATE3}.",
                "es": "En {CITY}, a {DATE3}.",
                "de": "{CITY}, den {DATE3}.",
            },
        ],
    },
    "tableau": {
        "domain": "PAYROLL",
        "glossary": True,
        "blocks": [
            {
                "fr": "Récapitulatif annuel de paie 2025",
                "en": "Annual payroll summary 2025",
                "ar": "الملخص السنوي للأجور 2025",
                "es": "Resumen anual de nóminas 2025",
                "de": "Jährliche Lohnübersicht 2025",
            },
            {"fr": "Mois", "en": "Month", "ar": "الشهر", "es": "Mes", "de": "Monat"},
            {lang: "[[gross_salary]]" for lang in LANGS},
            {lang: "[[social_contributions]]" for lang in LANGS},
            {lang: "[[net_salary]]" for lang in LANGS},
            {"fr": "Janvier", "en": "January", "ar": "يناير", "es": "Enero", "de": "Januar"},
            {lang: "{AMOUNT4}" for lang in LANGS},
            {lang: "{AMOUNT5}" for lang in LANGS},
            {lang: "{AMOUNT7}" for lang in LANGS},
            {
                "fr": "Total annuel",
                "en": "Annual total",
                "ar": "المجموع السنوي",
                "es": "Total anual",
                "de": "Jahressumme",
            },
            {
                "fr": "[[overtime]] : {N3} h",
                "en": "[[overtime]]: {N3} h",
                "ar": "[[overtime]]: {N3} ساعة",
                "es": "[[overtime]]: {N3} h",
                "de": "[[overtime]]: {N3} Std.",
            },
        ],
    },
}
# « scanne » : l'attestation avec un bruit d'OCR SIMULÉ (aucune numérisation réelle).
TEMPLATES["scanne"] = {"domain": "HR", "blocks": TEMPLATES["attestation"]["blocks"], "noise": True}


_HARAKAT = "\u064e\u064f\u0650\u0651"
_ARABIC_LETTER = re.compile("[\u0621-\u063a\u0641-\u064a]")


def fmt_amount(value: float, lang: str, *, arabic_digits: bool = False) -> str:
    whole, cents = f"{value:.2f}".split(".")
    groups = f"{int(whole):,}".split(",")
    sep = {"fr": "\u202f", "en": ",", "es": ".", "de": ".", "ar": ""}[lang]
    dec = {"fr": ",", "en": ".", "es": ",", "de": ",", "ar": ","}[lang]
    text = sep.join(groups) + dec + cents
    return to_arabic_digits(text) if arabic_digits else text


def fmt_date(day: int, month: int, year: int, lang: str, *, arabic_digits: bool = False) -> str:
    text = f"{day:02d}.{month:02d}.{year}" if lang == "de" else f"{day:02d}/{month:02d}/{year}"
    return to_arabic_digits(text) if arabic_digits else text


def to_arabic_digits(text: str) -> str:
    return text.translate(str.maketrans("0123456789,", "٠١٢٣٤٥٦٧٨٩٫"))


def surface(key: str, lang: str, form: str) -> tuple[str, str]:
    term, synonyms, variants = TERMS[key][lang]
    if form == "syn" and synonyms:
        return synonyms[0], "synonym"
    if form == "var" and variants:
        return variants[0], "variant"
    return term, "term"


def _strip_accents(text: str) -> str:
    keep = {"ñ", "Ñ"}
    out = []
    for ch in text:
        if ch in keep:
            out.append(ch)
            continue
        base = unicodedata.normalize("NFD", ch)
        out.append("".join(c for c in base if unicodedata.category(c) != "Mn"))
    return "".join(out)


def ocr_noise(text: str, lang: str) -> str:
    """Bruit d'OCR simulé, déterministe : perte d'accents, translittération, harakat, espaces."""
    if lang in ("fr", "es"):
        text = _strip_accents(text)
    elif lang == "de":
        text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("Ü", "Ue")
    elif lang == "ar":
        # Tatweel ou haraka insérés APRÈS une lettre arabe (jamais sur un mot latin ni une ponctuation).
        words = text.split(" ")
        noisy = []
        for i, word in enumerate(words):
            if len(word) > 3 and _ARABIC_LETTER.match(word[0]) and _ARABIC_LETTER.match(word[1]):
                mark = "\u0640" if i % 3 == 0 else _HARAKAT[i % 4]
                word = word[0] + mark + word[1:]
            noisy.append(word)
        text = " ".join(noisy)
    elif lang == "en":
        text = text.replace("certify", "cert1fy").replace("Done", "D one")
    return re.sub(r" ", "  ", text, count=2)


def render(
    text: str,
    lang: str,
    *,
    scanned: bool,
    terms_out: list,
    block_id: str,
    reference: dict | None = None,
) -> str:
    """Rend un gabarit. ``reference`` (dict de remplacements, éventuellement vide) : rendu de la
    référence candidate, toujours avec le terme principal validé du référentiel (ou du glossaire
    client), jamais avec un synonyme ou une variante."""
    arabic_digits = lang == "ar" and scanned

    def term_sub(match: re.Match) -> str:
        key, _, form = match.group(1).partition(":")
        if reference is not None:
            return reference.get(key) or TERMS[key][lang][0]
        value, kind = surface(key, lang, form)
        terms_out.append({"block": block_id, "key": key, "kind": kind, "surface": value})
        return value

    out = re.sub(r"\[\[([a-z_]+(?::[a-z]+)?)\]\]", term_sub, text)
    slots = {}
    for name, value in VALUES.items():
        slots[name] = value[lang]
    for name, value in AMOUNTS.items():
        slots[name] = fmt_amount(value, lang, arabic_digits=arabic_digits)
    for name, (d, m, y) in DATES.items():
        slots[name] = fmt_date(d, m, y, lang, arabic_digits=arabic_digits)
    slots.update(IDS)
    slots.update(NUMS)
    out = re.sub(r"\{([A-Z0-9]+)\}", lambda m: slots[m.group(1)], out)
    return ocr_noise(out, lang) if scanned else out


def slots_used(text: str) -> list[str]:
    return re.findall(r"\{([A-Z0-9]+)\}", text)


def referential_rows() -> list[dict]:
    rows = []
    for source, target in PAIRS:
        for spec in TERMS.values():
            term, synonyms, variants = spec[source]
            rows.append(
                {
                    "source_language": source,
                    "source_term": term,
                    "target_language": target,
                    "target_term": spec[target][0],
                    "synonyms": "|".join(synonyms),
                    "regional_variants": "|".join(variants),
                    "domain": spec["domain"],
                    "provenance": "corpus-synthetique-lot2",
                }
            )
        if (source, target) in AMBIGUOUS:
            word, targets, domain = AMBIGUOUS[(source, target)]
            for value in targets:
                rows.append(
                    {
                        "source_language": source,
                        "source_term": word,
                        "target_language": target,
                        "target_term": value,
                        "synonyms": "",
                        "regional_variants": "",
                        "domain": domain,
                        "provenance": "corpus-synthetique-lot2-ambigu",
                    }
                )
        word, value = SIBLING[(source, target)]
        rows.append(
            {
                "source_language": source,
                "source_term": word,
                "target_language": target,
                "target_term": value,
                "synonyms": "",
                "regional_variants": "",
                "domain": "INSURANCE",
                "provenance": "corpus-synthetique-lot2-domaine-frere",
            }
        )
    return rows


def build(out: Path, private_options: dict | None = None) -> dict:
    (out / "docs").mkdir(parents=True, exist_ok=True)
    (out / "expected").mkdir(parents=True, exist_ok=True)
    manifest = []
    for category, template in TEMPLATES.items():
        scanned = bool(template.get("noise"))
        for source, target in PAIRS:
            name = f"{category}-{source}-{target}"
            terms: list[dict] = []
            blocks, reference, numbers = [], {}, []
            for index, block in enumerate(template["blocks"], start=1):
                block_id = f"b{index:03d}"
                text = render(
                    block[source], source, scanned=scanned, terms_out=terms, block_id=block_id
                )
                ref = render(
                    block[target],
                    target,
                    scanned=False,
                    terms_out=[],
                    block_id=block_id,
                    reference=(
                        {"gross_salary": GLOSSARY_OVERRIDE[target]}
                        if template.get("glossary")
                        else {}
                    ),
                )
                blocks.append({"id": block_id, "text": text, "language": source})
                reference[block_id] = ref
                for slot in slots_used(block[source]):
                    kind = (
                        "amount"
                        if slot in AMOUNTS
                        else "date"
                        if slot in DATES
                        else "id"
                        if slot in IDS
                        else "number"
                        if slot in NUMS
                        else None
                    )
                    if kind:
                        numbers.append({"block": block_id, "slot": slot, "kind": kind})
            expected_terms = []
            for item in terms:
                tgt = TERMS[item["key"]][target][0]
                authority = "referential"
                if template.get("glossary") and item["key"] == "gross_salary":
                    tgt, authority = GLOSSARY_OVERRIDE[target], "client_glossary"
                expected_terms.append({**item, "expected_target": tgt, "authority": authority})
            options = {"target_language": target, "memory": {}, **(private_options or {})}
            if template.get("glossary"):
                options["glossary"] = [
                    {
                        "source": TERMS["gross_salary"][source][0],
                        "target": GLOSSARY_OVERRIDE[target],
                    }
                ]
                if source == "en":
                    options["glossary"].append(
                        {"source": "gross pay", "target": GLOSSARY_OVERRIDE[target]}
                    )
            ambiguous = []
            word = AMBIGUOUS.get((source, target), (None,))[0]
            if word and any(word in b["text"].lower() for b in blocks):
                ambiguous.append(word)
            sibling = SIBLING[(source, target)][0]
            ir = {
                "language": source,
                "domain": template["domain"],
                "pages": [{"number": 1, "blocks": blocks}],
            }
            (out / "docs" / f"{name}.json").write_text(
                json.dumps({"ir": ir, "options": options}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
            expected = {
                "document": name,
                "category": category,
                "domain": template["domain"],
                "source_language": source,
                "target_language": target,
                "simulated_ocr_noise": scanned,
                "terms": expected_terms,
                "numbers": numbers,
                "values": {
                    "amounts": {k: AMOUNTS[k] for k in AMOUNTS},
                    "dates": {k: list(v) for k, v in DATES.items()},
                    "ids": IDS,
                    "nums": NUMS,
                },
                "ambiguous_sources": ambiguous,
                "sibling_domain_source": sibling,
                "reference_candidate": reference,
                "reference_status": "SYNTHETIC_CANDIDATE_NOT_HUMAN_VALIDATED",
            }
            (out / "expected" / f"{name}.json").write_text(
                json.dumps(expected, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            manifest.append({"document": name, "category": category, "pair": f"{source}>{target}"})
    buffer = io.StringIO()
    fields = [
        "source_language",
        "source_term",
        "target_language",
        "target_term",
        "synonyms",
        "regional_variants",
        "domain",
        "provenance",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter=";", lineterminator="\n")
    writer.writeheader()
    rows = referential_rows()
    writer.writerows(rows)
    (out / "referential.csv").write_text(buffer.getvalue(), encoding="utf-8")
    summary = {
        "documents": len(manifest),
        "categories": sorted(TEMPLATES),
        "pairs": [f"{s}>{t}" for s, t in PAIRS],
        "referential_rows": len(rows),
        "terms": len(TERMS),
        "status": "SYNTHETIC — aucune donnée réelle ; références candidates non humaines",
    }
    (out / "manifest.json").write_text(
        json.dumps({"summary": summary, "documents": manifest}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--private-options",
        type=Path,
        default=None,
        help="JSON d'options moteur privé (hors dépôt) ajoutées à chaque document",
    )
    args = parser.parse_args(argv)
    out = args.out_dir.resolve()
    if out == ROOT or ROOT in out.parents:
        raise SystemExit("--out-dir doit être hors du dépôt (corpus généré non versionné)")
    options = json.loads(args.private_options.read_text()) if args.private_options else None
    print(json.dumps(build(out, options), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
