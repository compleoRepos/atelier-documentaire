"""Author-authored non-personal synthetic fixture only; not a real document."""
import asyncio
import json
import os
from pathlib import Path

import httpx
from app.ai.translation.interim_guard import synthetic_payload_sha256
from app.ai.translation.service import translate_blocks

ROOT=Path(__file__).resolve().parents[1]

def main():
    import argparse
    parser=argparse.ArgumentParser(description="Interim : fixture synthétique uniquement, aucune donnée du corpus dans la requête")
    parser.add_argument("--live",action="store_true")
    args=parser.parse_args()
    if not args.live:
        parser.error("--live requis pour cet appel synthétique explicite")
    (ROOT/"test-report/prompt-1").mkdir(parents=True,exist_ok=True)
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=30) as client:
        response=client.get(os.environ["OPENAI_API_BASE"].rstrip("/")+"/models",headers={"Authorization":"Bearer "+os.environ["OPENAI_API_KEY"]})
    if response.status_code!=200:
        raise RuntimeError("INTERIM_CATALOG_NOT_AVAILABLE")
    catalog=response.json()
    selected=next((m for m in catalog.get("data",[]) if m.get("id")=="gpt-5-mini"),None)
    if not selected or not selected.get("capabilities",{}).get("supports_response_format_json_schema"):
        raise RuntimeError("INTERIM_MODEL_NOT_AVAILABLE")
    fixture={'schema_version':'fixture/v1','synthetic_fixture_id':'SYNTH-MULTI-001','synthetic_fixture_authorized':True,
             'document_type':'SyntheticEmploymentFixture','domain':'HR','language':'en',
             'pages':[{'number':1,'blocks':[
                 {'id':'s-en','language':'en','text':'Employment Certificate. SYNTHETIC COMPANY certifies that SYNTHETIC PERSON A works here. Date 2026-01-02. Reference SYNTH-REF-001.'},
                 {'id':'s-ar','language':'ar','text':'هذه وثيقة تجريبية غير شخصية. عدد الصناديق ثلاثة.'},
                 {'id':'s-es','language':'es','text':'Este documento es una prueba sintética. Hay tres cajas azules.'},
             ]}]}
    options={'engine':'interim','interim_data_scope':'synthetic_fixture','target_language':'fr',
             'glossary':{'Employment Certificate':'Attestation de travail'},
             'protected_entities':['SYNTHETIC COMPANY','SYNTHETIC PERSON A','2026-01-02','SYNTH-REF-001']}
    options['interim_synthetic_payload_sha256_allowlist']=[synthetic_payload_sha256(fixture,options)]
    result=asyncio.run(translate_blocks(fixture,options))
    (ROOT/'test-report/prompt-1/interim-synthetic-live-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    assert not result['issues'], [x['code'] for x in result['issues']]
    assert set(result['translations'])=={'s-en','s-ar','s-es'}
    assert 'Attestation de travail' in result['translations']['s-en']
    assert all(entity in result['translations']['s-en'] for entity in options['protected_entities'])
    telemetry=result['translation_telemetry']
    assert telemetry['provider']=='interim' and telemetry['served_version']=='gpt-5-mini'
    assert telemetry['requests_sent']>=1 and telemetry['reference_validated'] is False
    for chunk in telemetry['chunks']:
        assert chunk['reserved_total_tokens']<=32768
        assert chunk['usage']['completion_tokens']<=8000
        assert chunk['usage']['total_tokens']<=32768
        assert chunk['reasoning_tokens'] is not None
    print(json.dumps({'synthetic_only':True,'provider':telemetry['provider'],'served_model':telemetry['served_version'],
                     'requests':telemetry['requests_sent'],'usage':telemetry['usage'],'blocks':3,
                     'entity_invariants':True,'schema_ids':True,'glossary_applied':True,'human_reference_validated':False},indent=2),flush=True)


if __name__=="__main__":
    main()
