"""LOT 2.4 — convertisseur d'export IATE (TBX) vers les CSV d'import du RAG.

L'export TBX ci-dessous est SYNTHÉTIQUE (fiches SYNTH-*, termes choisis pour le test) :
aucune donnée IATE n'est embarquée dans le dépôt.
"""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest

from .rag_support import grant, headers, make_rag_client

TOOLS = Path(__file__).resolve().parents[3] / "tools" / "rag_ue"
sys.path.insert(0, str(TOOLS))
import iate_tbx_to_csv as iate  # noqa: E402

sys.path.remove(str(TOOLS))

TBX_V2 = """<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX" xml:lang="en"><text><body>
 <termEntry id="SYNTH-1">
  <descripGrp><descrip type="subjectField">emploi</descrip></descripGrp>
  <langSet xml:lang="de">
   <tig><term>Arbeitszeit</term><termNote type="administrativeStatus">preferredTerm-admn-sts</termNote>
    <descrip type="reliabilityCode">3</descrip></tig>
   <tig><term>Dienstzeit</term><termNote type="administrativeStatus">admittedTerm-admn-sts</termNote>
    <descrip type="reliabilityCode">3</descrip></tig>
   <tig><term>Arbeitsdauer alt</term><termNote type="administrativeStatus">deprecatedTerm-admn-sts</termNote>
    <descrip type="reliabilityCode">4</descrip></tig>
   <tig><term>=SUMME(A1)</term><descrip type="reliabilityCode">4</descrip></tig>
  </langSet>
  <langSet xml:lang="fr">
   <tig><term>durée du travail</term><descrip type="reliabilityCode">2</descrip></tig>
   <tig><term>temps de travail</term><termNote type="administrativeStatus">preferredTerm-admn-sts</termNote>
    <descrip type="reliabilityCode">3</descrip></tig>
  </langSet>
  <langSet xml:lang="it">
   <tig><term>orario di lavoro</term><descrip type="reliabilityCode">2</descrip></tig>
  </langSet>
 </termEntry>
 <termEntry id="SYNTH-2">
  <langSet xml:lang="de"><tig><term>Kündigung</term><descrip type="reliabilityCode">4</descrip></tig></langSet>
 </termEntry>
</body></text></martif>
"""

TBX_V3 = """<?xml version="1.0" encoding="UTF-8"?>
<tbx xmlns="urn:iso:std:iso:30042:ed-2" type="TBX-Basic" style="dca" xml:lang="en"><text><body>
 <conceptEntry id="SYNTH-3">
  <langSec xml:lang="es"><termSec><term>trabajador cedido</term>
   <termNote type="administrativeStatus">preferredTerm-admn-sts</termNote>
   <descrip type="reliabilityCode">4</descrip></termSec></langSec>
  <langSec xml:lang="fr"><termSec><term>travailleur intérimaire</term>
   <descrip type="reliabilityCode">3</descrip></termSec></langSec>
 </conceptEntry>
</body></text></tbx>
"""


def _convert(text: str, **kwargs):
    options = {"min_reliability": 3, "export_date": "2026-11-03", "domain": "HR", **kwargs}
    return iate.convert(text.encode("utf-8"), **options)


def test_tbx_v2_reliability_status_preferred_and_formula_rules():
    result = _convert(TBX_V2)
    assert result["stats"] == {"concepts": 2, "without_french": 1}
    (row,) = result["rows"]["de"]
    assert (row["source_term"], row["target_term"]) == ("Arbeitszeit", "temps de travail")
    assert row["synonyms"] == "Dienstzeit"  # déprécié et formule écartés
    assert row["provenance"].startswith("IATE, Union européenne, fiche SYNTH-1, fiabilité 3")
    assert row["usage_context"] == "IATE, domaine emploi" and row["domain"] == "HR"
    assert result["rows"]["it"] == []  # fiabilité 2 < 3
    relaxed = _convert(TBX_V2, min_reliability=2)
    assert [r["source_term"] for r in relaxed["rows"]["it"]] == ["orario di lavoro"]


def test_tbx_v3_namespaced_concept_entries():
    result = _convert(TBX_V3)
    (row,) = result["rows"]["es"]
    assert (row["source_term"], row["target_term"]) == (
        "trabajador cedido",
        "travailleur intérimaire",
    )
    assert "fiche SYNTH-3, fiabilité 3" in row["provenance"]


def test_xml_entities_are_refused():
    with pytest.raises(ValueError, match="entité"):
        _convert('<!DOCTYPE m [<!ENTITY a "x">]><martif>&a;</martif>')


def test_converted_rows_pass_the_product_importer(app_env, monkeypatch, tmp_path):
    tbx = tmp_path / "export.tbx"
    tbx.write_text(TBX_V2, encoding="utf-8")
    assert (
        iate.main(
            ["--tbx", str(tbx), "--out", str(tmp_path / "out"), "--export-date", "2026-11-03"]
        )
        == 0
    )
    data = (tmp_path / "out" / "iate-de-fr.csv").read_bytes()
    assert len(list(csv.DictReader(io.StringIO(data.decode()), delimiter=";"))) == 1
    client, _app, ids = make_rag_client(monkeypatch, mode="SHADOW")
    grant(client, "admin-a", ids["admin-a"], "rag_admin")
    grant(client, "admin-a", ids["admin-a"], "terminology_manager")
    h = headers(client, "admin-a")
    ref = client.post(
        "/api/rag-admin/referentials", headers=h, json={"kind": "linguistic", "name": "IATE"}
    ).json()
    draft = client.post(f"/api/rag-admin/referentials/{ref['id']}/versions", headers=h, json={})
    response = client.post(
        f"/api/rag-admin/versions/{draft.json()['id']}/import",
        params={"format": "csv", "dry_run": "true"},
        content=data,
        headers={**h, "Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["error_count"], body["accepted_count"]) == (0, 1), body["report"]
