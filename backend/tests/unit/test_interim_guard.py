from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from app.ai.translation.interim_guard import authorize_interim_fixture, synthetic_payload_sha256
from app.ai.translation.service import translate_blocks
from app.core.settings import Settings


class GPTDouble:
    def encode(self,value,**kwargs):
        return list(range(max(1,len(value)//4)))


def fixture():
    return {'language':'en','domain':'HR','synthetic_fixture_authorized':True,
            'pages':[{'number':1,'blocks':[{'id':'s1','text':'Synthetic employment document for test only.','language':'en'}]}]}


def opts(ir,**values):
    options={'engine':'interim','interim_data_scope':'synthetic_fixture',**values}
    options['interim_synthetic_payload_sha256_allowlist']=[synthetic_payload_sha256(ir,options)]
    return options


@pytest.mark.asyncio
@pytest.mark.parametrize('index',range(8))
async def test_corpus_sha_refusal_precedes_any_network_or_provider_construction(index,tmp_path,monkeypatch):
    inputs=tmp_path/'input'
    inputs.mkdir()
    source=inputs/f'local-{index}.pdf'
    source.write_bytes(f'fake confidential corpus input {index}'.encode())
    ir=fixture()
    ir['versions']={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
    def forbidden(*args,**kwargs):
        raise AssertionError('No HTTP request is allowed')
    monkeypatch.setattr(httpx.AsyncClient,'post',forbidden)
    result=await translate_blocks(ir,opts(ir,_corpus_input_dir=inputs))
    assert result['issues'][0]['code']=='INTERIM_REAL_CORPUS_FORBIDDEN'
    assert result['translation_telemetry']['requests_sent']==0
    assert result['translation_telemetry']['execution_status']=='NOT_EXECUTED'
    assert result['translation_telemetry']['provider']=='interim'


def test_unmarked_fixture_unknown_hash_and_added_personal_context_are_rejected(tmp_path):
    ir=fixture()
    options=opts(ir,_corpus_input_dir=tmp_path)
    assert authorize_interim_fixture(ir,options) is None
    ir['synthetic_fixture_authorized']=False
    assert authorize_interim_fixture(ir,options)=='INTERIM_SYNTHETIC_FIXTURE_REQUIRED'
    ir['synthetic_fixture_authorized']=True
    ir['pages'][0]['blocks'][0]['text']='Unapproved replacement payload'
    assert authorize_interim_fixture(ir,options)=='INTERIM_SYNTHETIC_PAYLOAD_NOT_ALLOWLISTED'
    ir=fixture()
    options=opts(ir,_corpus_input_dir=tmp_path)
    options['memory']={'private source':'private target'}
    assert authorize_interim_fixture(ir,options)=='INTERIM_SYNTHETIC_PAYLOAD_NOT_ALLOWLISTED'


@pytest.mark.parametrize('environment',['production','prod','private'])
def test_interim_refused_in_private_or_production(environment):
    with pytest.raises(ValueError):
        Settings(environment=environment,engine='interim')


def test_secret_configuration_is_server_only_and_total_cap_has_no_unverified_override():
    settings=Settings(engine='interim',interim_api_key='not-public',interim_api_base='https://proxy.test/v1')
    assert 'not-public' not in repr(settings)
    assert 'interim_api_key' not in settings.model_dump()
    assert 'interim_api_base' not in settings.model_dump()
    assert settings.interim_total_generation_cap_verified is True
    assert Settings(engine='interim').interim_capability_proof is None


@pytest.mark.asyncio
async def test_authorized_fixture_still_fails_closed_when_total_generation_cap_is_unproven(tmp_path):
    ir=fixture()
    seen=[]
    result=await translate_blocks(ir,opts(ir,_corpus_input_dir=tmp_path,interim_api_base='https://interim.test/v1',
                interim_total_generation_cap_verified=False,tokenizer=GPTDouble(),transport=httpx.MockTransport(lambda r:seen.append(r))))
    assert seen==[]
    assert any(x['code']=='INTERIM_TOTAL_GENERATION_CAP_NOT_VERIFIED' for x in result['issues'])
    assert result['translation_telemetry']['provider']=='interim'
    assert result['versions']['model']=='gpt-5-mini'
    assert result['translations']['s1']==ir['pages'][0]['blocks'][0]['text']


@pytest.mark.asyncio
async def test_authorized_synthetic_service_routes_only_to_interim_mock(tmp_path):
    ir=fixture()
    seen=[]
    def response(request):
        body=json.loads(request.content)
        seen.append(body)
        assert body['model']=='gpt-5-mini'
        assert 'max_tokens' not in body
        return httpx.Response(200,json={'model':'gpt-5-mini','choices':[{'finish_reason':'stop','message':{'content':json.dumps({'translations':[{'id':'s1','text':'Document synthétique à usage de test uniquement.'}]})}}],
          'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'completion_tokens_details':{'reasoning_tokens':0}}})
    result=await translate_blocks(ir,opts(ir,_corpus_input_dir=tmp_path,tokenizer=GPTDouble(),
         interim_api_base='https://interim.test/v1',transport=httpx.MockTransport(response),
         interim_total_generation_cap_verified=True,interim_capability_proof='MOCK_ONLY_CAP_CONTRACT'))
    assert len(seen)==1
    assert result['translations']['s1'].startswith('Document synthétique')
    assert result['translation_telemetry']['provider']=='interim'
    assert result['translation_telemetry']['served_version']=='gpt-5-mini'
    assert result['translation_telemetry']['data_boundary']=='outside_private_cloud'
    assert result['translation_telemetry']['reference_validated'] is False
    assert result['translation_telemetry']['chunks'][0]['reasoning_tokens']==0


def test_stage_projection_does_not_claim_interim_gate_success():
    from types import SimpleNamespace

    from app.api.routes import _stage_projection
    doc=SimpleNamespace(status='REVIEW_REQUIRED',analysis_json={'pages':[]},translation_json={'translations':{}},
              issues_json=[{'code':'INTERIM_REAL_CORPUS_FORBIDDEN','severity':'critical'}],review_version=1,quality_json={})
    stages=_stage_projection(doc)
    translation=next(x for x in stages if x['id']=='translation')
    assert translation['state']=='failed'
    assert translation['evidence']=='interim_gate_blocked'
