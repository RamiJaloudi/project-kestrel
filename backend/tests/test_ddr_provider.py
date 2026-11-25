"""No paid requests: stage/credential/transport tests use synthetic SDK responses."""
import copy
import json
import logging
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
pytest.importorskip('langchain_openai')
from kestrel.adapters import ddr_provider as provider, provider_secrets
from kestrel.ddr.schemas import RunSpec, Limits, QualityReview, Claim, Citation, canonical, digest
from kestrel.schemas.agent_registry import Definition
from kestrel.adapters.extraction import canonical as config_canonical


def live_config(matter=None):
    matter=matter or str(uuid.uuid4());profiles=[]
    for index,role in enumerate(['contracts','drafter','quality']):
        definition=Definition(agent_kind=role,provider='openai',model=provider.MODEL,
            prompt='Published synthetic '+role+' stage: preserve exact reviewed evidence and flag missing facts.',
            tools=sorted(provider.REQUIRED[role]),timeout_seconds=17+index,max_output_tokens=800+index*100,total_tokens=16000)
        profiles.append({'id':str(uuid.uuid4()),'profile_id':str(uuid.uuid4()),'matter_id':matter,
            'content_hash':str(index+1)*64,'definition':definition.model_dump(mode='json')})
    value={'engine':'openai','agent_profiles':profiles,'agent_profile_ids':[item['id'] for item in profiles],
        'agent_profiles_hash':digest(config_canonical(profiles)),'automatic_paid_retries':0,'max_cost_cents':200,
        'total_tokens':16000,'max_output_tokens':800,'max_model_calls':3,'max_concurrency':2}
    value['live_provider_manifest']=provider.manifest(value)
    return value


def spec(config):
    return RunSpec(run_id=str(uuid.uuid4()),requester_id=str(uuid.uuid4()),matter_id=str(uuid.uuid4()),
        snapshot_hash='a'*64,config_hash=digest(config_canonical(config)),finding_refs=('finding',),deadline_epoch=2000000000,
        limits=Limits(total_tokens=16000,max_output_tokens=800))


def test_manifest_binds_three_stage_definitions_model_tools_and_prices():
    config=live_config();assert set(provider.validate_config(config))=={'contracts','drafter','quality'}
    assert provider.pricing_manifest()['input_cents_per_million']==75
    assert provider.pricing_manifest()['output_cents_per_million']==450
    for change in ['prompt','timeout_seconds','model','tools','missing_stage','pricing']:
        altered=copy.deepcopy(config)
        if change=='prompt':altered['agent_profiles'][0]['definition']['prompt']+=' Changed after pin'
        elif change=='timeout_seconds':altered['agent_profiles'][0]['definition']['timeout_seconds']=59
        elif change=='model':altered['agent_profiles'][0]['definition']['model']='unapproved-model'
        elif change=='tools':altered['agent_profiles'][0]['definition']['tools']=['request_attorney_review']
        elif change=='missing_stage':altered['agent_profiles'].pop()
        else:altered['live_provider_manifest']['pricing']['input_cents_per_million']=1
        with pytest.raises(ValueError):provider.factory(altered)


def test_factory_and_availability_never_use_ambient_key_or_url(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','AMBIENT_CANARY_KEY');monkeypatch.setenv('OPENAI_BASE_URL','https://unapproved.invalid')
    monkeypatch.setattr(provider_secrets,'configured',lambda:None)
    assert not provider.availability()['enabled']
    value=provider.factory(live_config())
    with pytest.raises(PermissionError):value.invoke(spec(live_config()),'quality',{},800)
    config=live_config();value=provider.factory(config)
    with pytest.raises(PermissionError,match='LIVE_PROVIDER_DISABLED'):value.invoke(spec(config),'quality',{},800)


def test_each_stage_consumes_published_prompt_model_timeout_and_output_bound(monkeypatch):
    config=live_config();value=provider.factory(config);captured=[]
    monkeypatch.setattr(provider_secrets,'configured',lambda:(True,'MOCK_PRIVATE_KEY'))
    @contextmanager
    def model(key,model,timeout,bound):
        item={'key':key,'model':model,'timeout':timeout,'bound':bound};captured.append(item)
        class Structured:
            def invoke(self,messages,config):
                item['messages']=messages;item['callbacks']=config['callbacks']
                return {'raw':SimpleNamespace(usage_metadata={'input_tokens':100,'output_tokens':20},response_metadata={'model_name':provider.MODEL}),
                    'parsed':item['schema'](), 'parsing_error':None}
        class Model:
            def with_structured_output(self,schema,**kwargs):
                citation=Citation(evidence_id='evidence',finding_ref='finding',source_version_id='source',source_bytes_hash='a'*64,source_text_hash='b'*64,unit=1,start=0,end=9,quote='Synthetic')
                claim=Claim(finding_ref='finding',text='Synthetic reviewed finding',severity='unrated',citations=(citation,))
                fields={'claims':(claim,)} if item['stage']=='contracts' else {'title':'Synthetic draft','claims':(claim,)} if item['stage']=='draft' else {'passed':True,'issues':()}
                item['schema']=lambda:schema(**fields)
                item['structured']=kwargs
                return Structured()
        item['stage']=['contracts','draft','quality'][len(captured)-1]
        yield Model()
    monkeypatch.setattr(provider,'_model_client',model)
    for stage,(_,schema) in provider.STAGES.items():
        result=value.invoke(spec(config),stage,{'synthetic':'untrusted payload'},800)
        assert result.usage.cost_cents==1
    for index,item in enumerate(captured):
        assert item['model']==provider.MODEL and item['timeout']==17+index and item['bound']==800
        assert item['messages'][1].content==config['agent_profiles'][index]['definition']['prompt']
        assert item['callbacks']==[] and item['structured']=={'method':'json_schema','strict':True,'include_raw':True}


def test_real_langchain_sdk_request_is_fixed_private_bounded_and_not_logged(monkeypatch,caplog):
    import httpx
    config=live_config();value=provider.factory(config);requests=[]
    config['agent_profiles'][2]['definition']['prompt']+=' Prüfe Kündigung und Übertragung; ändere keine genehmigte Bewertung.'
    config['agent_profiles_hash']=digest(config_canonical(config['agent_profiles']));config['live_provider_manifest']=provider.manifest(config);value=provider.factory(config)
    monkeypatch.setattr(provider_secrets,'configured',lambda:(True,'MOCK_PRIVATE_KEY'))
    for key in ['OPENAI_BASE_URL','OPENAI_API_BASE','HTTP_PROXY','HTTPS_PROXY']:
        monkeypatch.setenv(key,'https://unapproved.invalid')
    monkeypatch.setenv('OPENAI_ORG_ID','AMBIENT_ORG');monkeypatch.setenv('OPENAI_PROJECT_ID','AMBIENT_PROJECT')
    def handle(self,request):
        requests.append(request)
        return httpx.Response(200,json={'id':'synthetic-completion','object':'chat.completion','created':1,'model':provider.MODEL,
            'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':canonical(QualityReview(passed=True,issues=()))}}],
            'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}},request=request)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',handle)
    with caplog.at_level(logging.DEBUG):result=value.invoke(spec(config),'quality',{'synthetic':'SYNTHETIC_PAYLOAD_CANARY'},800)
    assert result.artifact.passed and result.usage.input_tokens==100 and len(requests)==1
    request=requests[0];body=json.loads(request.content)
    assert str(request.url)=='https://api.openai.com/v1/chat/completions'
    assert request.headers['authorization']=='Bearer MOCK_PRIVATE_KEY'
    assert 'openai-organization' not in request.headers and 'openai-project' not in request.headers
    assert body['model']==provider.MODEL and body['store'] is False and body['reasoning_effort']=='none'
    assert body.get('tools',[])==[] and body['response_format']['type']=='json_schema'
    assert body['max_completion_tokens']==800
    assert 'SYNTHETIC_PAYLOAD_CANARY' not in caplog.text and 'MOCK_PRIVATE_KEY' not in caplog.text


def test_sdk_error_is_sent_once_without_retry_and_unknown_usage_rejected(monkeypatch):
    import httpx
    config=live_config();value=provider.factory(config);calls=[]
    monkeypatch.setattr(provider_secrets,'configured',lambda:(True,'MOCK_PRIVATE_KEY'))
    def handle(self,request):calls.append(True);return httpx.Response(500,json={'error':{'message':'synthetic provider fault'}},request=request)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',handle)
    with pytest.raises(Exception):value.invoke(spec(config),'quality',{},800)
    assert len(calls)==1


def test_long_published_prompt_is_bounded_before_sdk_or_secret_read(monkeypatch):
    config=live_config();config['agent_profiles'][2]['definition']['prompt']='界'*11000
    config['agent_profiles_hash']=digest(config_canonical(config['agent_profiles']));config['live_provider_manifest']=provider.manifest(config)
    value=provider.factory(config)
    monkeypatch.setattr(provider_secrets,'configured',lambda:pytest.fail('must reject before credential read or network'))
    with pytest.raises(ValueError,match='PROVIDER_INPUT_BOUND'):value.invoke(spec(config),'quality',{},800)


@pytest.mark.parametrize('change',['no_usage','wrong_model','invalid_json','oversized'])
def test_uncertain_sdk_completions_are_never_retried_or_exposed(monkeypatch,change):
    import httpx
    config=live_config();value=provider.factory(config);calls=[]
    monkeypatch.setattr(provider_secrets,'configured',lambda:(True,'MOCK_PRIVATE_KEY'))
    def handle(self,request):
        calls.append(True)
        if change=='oversized':return httpx.Response(200,content=b'x'*512001,request=request)
        body={'id':'synthetic','object':'chat.completion','created':1,'model':provider.MODEL,
            'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':canonical(QualityReview(passed=True,issues=()))}}],
            'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}}
        if change=='no_usage':body.pop('usage')
        if change=='wrong_model':body['model']='unapproved-model'
        if change=='invalid_json':body['choices'][0]['message']['content']='SYNTHETIC_INVALID_RESPONSE_CANARY'
        return httpx.Response(200,json=body,request=request)
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',handle)
    with pytest.raises(ValueError) as error:value.invoke(spec(config),'quality',{},800)
    assert str(error.value)=='PROVIDER_COMPLETION_UNCERTAIN' and calls==[True]
