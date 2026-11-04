"""Lexiques de type de document des langues de l'UE ajoutées (LOT 2.3).

Fichier GÉNÉRÉ à partir des libellés préférentiels officiels d'EuroVoc 4.24
(Office des publications de l'Union européenne, licence CC BY 4.0) ; modifié :
minuscules, qualificatifs entre parenthèses retirés. Un descripteur par
concept français cité en commentaire. Consulté uniquement pour une langue
détectée dans le document (voir ``classification._score``) : sans effet sur
les documents en langues historiques.
"""

from __future__ import annotations

EUROVOC_VERSION = "4.24"
# type de document -> descripteurs EuroVoc (libellé français officiel)
DESCRIPTORS = {
    "employment_certificate": (
        ("3843", "salaire"),
        ("735", "employeur"),
        ("3854", "salarié"),
        ("3273", "rémunération du travail"),
    ),
    "contract": (
        ("166", "contrat de travail"),
        ("164", "contrat"),
        ("194", "convention collective"),
        ("2602", "prestation de services"),
    ),
    "bank_statement": (("4738", "banque"), ("285", "crédit")),
    "invoice": (("957", "facturation"), ("4585", "TVA"), ("1078", "fournisseur")),
    "diploma": (
        ("446", "diplôme"),
        ("4151", "université"),
        ("800", "enseignement supérieur"),
        ("1074", "formation professionnelle"),
    ),
    "administrative_form": (("1076", "formulaire"), ("77", "administration publique")),
}

EU_TYPE_LEXICONS: dict[str, dict[str, tuple[str, ...]]] = {
    "employment_certificate": {
        "bul": (
            "заплащане",
            "работодател",
            "наемен работник",
            "трудово възнаграждение",
        ),
        "ces": (
            "mzda",
            "zaměstnavatel",
            "zaměstnanec",
            "odměňování",
        ),
        "dan": (
            "løn",
            "arbejdsgiver",
            "lønmodtager",
            "aflønning af arbejde",
        ),
        "ell": (
            "μισθός",
            "εργοδότης",
            "μισθωτός",
            "απολαβές από την εργασία",
        ),
        "est": (
            "palk",
            "tööandja",
            "palgatöötaja",
            "töö tasustamine",
        ),
        "fin": (
            "palkka",
            "työnantaja",
            "palkansaaja",
            "korvaus työstä",
        ),
        "gle": (
            "pá",
            "fostóir",
            "saothraí pá",
            "luach saothair as obair",
        ),
        "hrv": (
            "plaća",
            "poslodavac",
            "radnik koji zarađuje plaću",
            "nagrađivanje za rad",
        ),
        "hun": (
            "díjazás",
            "munkaadó",
            "alkalmazott",
            "munkaviszonyból származó jövedelem",
        ),
        "lav": (
            "atalgojums",
            "darba devējs",
            "algots strādnieks",
            "atlīdzība par darbu",
        ),
        "lit": (
            "darbo užmokestis",
            "darbdavys",
            "pagal darbo sutartį dirbantis darbuotojas",
            "atlyginimas už darbą",
        ),
        "mlt": (
            "paga",
            "impjegatur",
            "persuna b'paga",
            "rimunerazzojni għax-xogħol",
        ),
        "pol": (
            "płaca",
            "pracodawca",
            "pracownik",
            "wynagrodzenie za pracę",
        ),
        "por": (
            "salário",
            "empregador",
            "assalariado",
            "remuneração do trabalho",
        ),
        "ron": (
            "plată",
            "patron",
            "salariat",
            "remunerația muncii",
        ),
        "slk": (
            "mzda",
            "zamestnávateľ",
            "zárobkovo činná osoba",
            "odmena za prácu",
        ),
        "slv": (
            "plača",
            "delodajalec",
            "delojemalec",
            "plačilo za delo",
        ),
        "swe": (
            "lön",
            "arbetsgivare",
            "arbetstagare",
            "ersättning för arbete",
        ),
    },
    "contract": {
        "bul": (
            "трудов договор",
            "договор",
            "колективна конвенция",
            "предоставяне на услуги",
        ),
        "ces": (
            "pracovní smlouva",
            "smlouva",
            "kolektivní smlouva",
            "poskytování služeb",
        ),
        "dan": (
            "arbejdskontrakt",
            "kontrakt",
            "kollektiv overenskomst",
            "udførelse af tjenesteydelser",
        ),
        "ell": (
            "σύμβαση εργασίας",
            "σύμβαση",
            "συλλογική σύμβαση εργασίας",
            "παροχή υπηρεσιών",
        ),
        "est": (
            "tööleping",
            "leping",
            "kollektiivleping",
            "teenuste pakkumine",
        ),
        "fin": (
            "työsopimus",
            "sopimus",
            "kollektiivinen sopimus",
            "palvelujen tarjoaminen",
        ),
        "gle": (
            "conradh oibre",
            "conradh",
            "comhaontú comhchoiteann",
            "seirbhísí a sholáthar",
        ),
        "hrv": (
            "ugovor o radu",
            "ugovor",
            "kolektivni ugovor",
            "pružanje usluga",
        ),
        "hun": (
            "munkaszerződés",
            "szerződés",
            "kollektív szerződés",
            "szolgáltatásnyújtás",
        ),
        "lav": (
            "darba līgums",
            "līgums",
            "koplīgums",
            "pakalpojumu nodrošināšana",
        ),
        "lit": (
            "darbo sutartis",
            "sutartis",
            "kolektyvinė sutartis",
            "paslaugų teikimas",
        ),
        "mlt": (
            "kuntratt tax-xogħol",
            "kuntratt",
            "ftehim kollettiv",
            "provdiment ta’ servizzi",
        ),
        "pol": (
            "umowa o pracę",
            "umowa cywilna",
            "układ zbiorowy",
            "świadczenie usług",
        ),
        "por": (
            "contrato de trabalho",
            "contrato",
            "contrato coletivo",
            "prestação de serviços",
        ),
        "ron": (
            "contract de muncă",
            "contract",
            "acord colectiv",
            "ofertă de servicii",
        ),
        "slk": (
            "pracovná zmluva",
            "zmluva",
            "kolektívna zmluva",
            "poskytovanie služieb",
        ),
        "slv": (
            "pogodba o delu",
            "pogodba",
            "kolektivna pogodba",
            "opravljanje storitev",
        ),
        "swe": (
            "arbetsavtal",
            "avtal",
            "kollektivavtal",
            "tillhandahållande av tjänster",
        ),
    },
    "bank_statement": {
        "bul": (
            "банка",
            "кредит",
        ),
        "ces": (
            "banka",
            "úvěr",
        ),
        "dan": (
            "bank",
            "kredit",
        ),
        "ell": (
            "τράπεζα",
            "πίστη",
        ),
        "est": (
            "pank",
            "krediit",
        ),
        "fin": (
            "pankki",
            "luotto",
        ),
        "gle": (
            "banc",
            "creidmheas",
        ),
        "hrv": (
            "banka",
            "kredit",
        ),
        "hun": (
            "bank",
            "hitel",
        ),
        "lav": (
            "banka",
            "kredīts",
        ),
        "lit": (
            "bankas",
            "kreditas",
        ),
        "mlt": (
            "bank",
            "kreditu",
        ),
        "pol": (
            "bank",
            "kredyt",
        ),
        "por": (
            "banco",
            "crédito",
        ),
        "ron": (
            "bancă",
            "credit",
        ),
        "slk": (
            "banka",
            "úver",
        ),
        "slv": (
            "banka",
            "kredit",
        ),
        "swe": (
            "bank",
            "kredit",
        ),
    },
    "invoice": {
        "bul": (
            "фактуриране",
            "ддс",
            "доставчик",
        ),
        "ces": (
            "fakturace",
            "daň z přidané hodnoty",
            "dodavatel",
        ),
        "dan": (
            "fakturering",
            "moms",
            "leverandør",
        ),
        "ell": (
            "τιμολόγηση",
            "φπα",
            "προμηθευτής",
        ),
        "est": (
            "arveldus",
            "käibemaks",
            "tarnija",
        ),
        "fin": (
            "laskutus",
            "alv",
            "tavarantoimittaja",
        ),
        "gle": (
            "sonrascadh",
            "cbl",
            "soláthróir",
        ),
        "hrv": (
            "fakturiranje",
            "pdv",
            "dobavljač",
        ),
        "hun": (
            "számlázás",
            "hozzáadottérték-adó",
            "szállító",
        ),
        "lav": (
            "faktūrrēķina izrakstīšana",
            "pvn",
            "piegādātājs",
        ),
        "lit": (
            "sąskaitos faktūros pateikimas",
            "pvm",
            "tiekėjas",
        ),
        "mlt": (
            "fatturar",
            "taxxa fuq il-valur miżjud",
            "fornitur",
        ),
        "pol": (
            "faktura",
            "vat",
            "dostawca",
        ),
        "por": (
            "faturação",
            "iva",
            "fornecedor",
        ),
        "ron": (
            "facturare",
            "tva",
            "furnizori",
        ),
        "slk": (
            "fakturácia",
            "dph",
            "dodávateľ",
        ),
        "slv": (
            "izstavljanje računov",
            "ddv",
            "dobavitelj",
        ),
        "swe": (
            "fakturering",
            "moms",
            "leverantör",
        ),
    },
    "diploma": {
        "bul": (
            "диплома",
            "университет",
            "висше образование",
            "професионално обучение",
        ),
        "ces": (
            "vysvědčení",
            "univerzita",
            "vysokoškolské vzdělání",
            "profesní příprava",
        ),
        "dan": (
            "eksamensbevis",
            "universitet",
            "højere uddannelse",
            "erhvervsuddannelse",
        ),
        "ell": (
            "τίτλος σπουδών",
            "πανεπιστήμιο",
            "ανώτατη εκπαίδευση",
            "επαγγελματική κατάρτιση",
        ),
        "est": (
            "diplom",
            "ülikool",
            "kõrgharidus",
            "kutseõpe",
        ),
        "fin": (
            "tutkintotodistus",
            "korkeakoulu",
            "korkeakouluopetus",
            "ammatillinen koulutus",
        ),
        "gle": (
            "dioplóma",
            "ollscoil",
            "ardoideachas",
            "gairmoiliúint",
        ),
        "hrv": (
            "diploma",
            "sveučilište",
            "visokoškolsko obrazovanje",
            "strukovna izobrazba",
        ),
        "hun": (
            "oklevél",
            "egyetem",
            "felsőoktatás",
            "szakképzés",
        ),
        "lav": (
            "diploms",
            "akadēmiskā augstskola",
            "augstākā izglītība",
            "arodapmācība",
        ),
        "lit": (
            "diplomas",
            "universitetas",
            "aukštasis mokslas",
            "profesinis mokymas",
        ),
        "mlt": (
            "diploma",
            "università",
            "edukazzjoni għolja",
            "taħriġ vokazzjonali",
        ),
        "pol": (
            "dyplom",
            "uniwersytet",
            "szkolnictwo wyższe",
            "szkolenie zawodowe",
        ),
        "por": (
            "diploma",
            "universidade",
            "ensino superior",
            "formação profissional",
        ),
        "ron": (
            "diplomă",
            "universitate",
            "învățământ superior",
            "formare profesională",
        ),
        "slk": (
            "diplom",
            "univerzita",
            "vyššie vzdelávanie",
            "odborná príprava",
        ),
        "slv": (
            "diploma",
            "univerza",
            "visokošolsko izobraževanje",
            "poklicno usposabljanje",
        ),
        "swe": (
            "examensbevis",
            "universitet",
            "högre utbildning",
            "yrkesutbildning",
        ),
    },
    "administrative_form": {
        "bul": (
            "формуляр",
            "държавна администрация",
        ),
        "ces": (
            "formulář",
            "veřejná správa",
        ),
        "dan": (
            "formular",
            "offentlig forvaltning",
        ),
        "ell": (
            "έντυπο",
            "δημόσια διοίκηση",
        ),
        "est": (
            "plank",
            "avalik haldus",
        ),
        "fin": (
            "lomake",
            "julkinen hallinto",
        ),
        "gle": (
            "foirm",
            "riarachán poiblí",
        ),
        "hrv": (
            "obrazac",
            "javna uprava",
        ),
        "hun": (
            "formanyomtatvány",
            "közigazgatás",
        ),
        "lav": (
            "veidlapa",
            "valsts pārvalde",
        ),
        "lit": (
            "blankas",
            "viešasis valdymas",
        ),
        "mlt": (
            "formola",
            "amministrazzjoni pubblika",
        ),
        "pol": (
            "formularz",
            "administracja publiczna",
        ),
        "por": (
            "formulário",
            "administração pública",
        ),
        "ron": (
            "tipizat",
            "administrație publică",
        ),
        "slk": (
            "formulár",
            "štátna správa",
        ),
        "slv": (
            "obrazec",
            "javna uprava",
        ),
        "swe": (
            "formulär",
            "offentlig förvaltning",
        ),
    },
}
