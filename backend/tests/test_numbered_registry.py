from sqlalchemy import select
from test_auth_policy import env,login
from test_administration import post
from kestrel.models import Account,MatterAssignment,EthicalWall
from kestrel.services.auth import clock

def test_composite_numbers_preserve_zeroes_and_are_unique_per_client(env):
    http,sessions,ids,_=env
    csrf=login(http,'root').json()['csrf_token']
    client=post(http,'/clients',csrf,{'name':'Numbered synthetic client','client_number':'012345'})
    assert client.status_code==201 and client.json()['client_number']=='012345'
    c=client.json()['id']
    m=post(http,'/matters',csrf,{'name':'Numbered matter','client_id':c,'matter_number':'789012'})
    assert m.status_code==201 and m.json()['client_matter_number']=='012345-789012'
    assert post(http,'/matters',csrf,{'name':'Duplicate pair','client_id':c,'matter_number':'789012'}).status_code==409
    assert post(http,'/clients',csrf,{'name':'Duplicate client','client_number':'012345'}).status_code==409
    c2=post(http,'/clients',csrf,{'name':'Another client','client_number':'012346'}).json()['id']
    assert post(http,'/matters',csrf,{'name':'Same matter number','client_id':c2,'matter_number':'789012'}).status_code==201
    assert post(http,'/clients',csrf,{'name':'Number as integer','client_number':12345}).status_code==422
    assert post(http,'/clients',csrf,{'name':'Bad number','client_number':'123-45'}).status_code==422
    row=next(r for r in http.get('/api/v1/validation/matters').json() if r['matter_id']==m.json()['id'])
    assert row['client_matter_number']=='012345-789012'

def test_number_resolution_validity_walls_and_uuid_compatibility(env):
    http,sessions,ids,_=env
    csrf=login(http,'root').json()['csrf_token']
    c=post(http,'/clients',csrf,{'name':'Reference numbered client','client_number':'012345'}).json()['id']
    m=post(http,'/matters',csrf,{'name':'Reference numbered matter','client_id':c,'matter_number':'789012'}).json()['id']
    post(http,f'/matters/{m}/decision',csrf,{'status':'validated','expected_revision':1,'rationale':'Synthetic validation completed'})
    with sessions() as db:
        db.add(MatterAssignment(account_id=ids['lawyer'],matter_id=m,expires_at=clock()+1000))
        db.get(Account,ids['lawyer']).email='lawyer@demo.example';db.commit()
    headers={'origin':'https://firm.localhost','x-csrf-token':csrf}
    for pair in [{'clientId':'012345','matterId':'789012'},{'clientId':c,'matterId':m}]:
        response=http.post('/api/client-matter-validations',json=pair,headers=headers)
        assert response.json()['valid'] and response.json()['clientMatterId']=='012345-789012'
        wall=http.post('/api/ethical-walls',json={**pair,'emails':['lawyer@demo.example']},headers=headers)
        assert wall.status_code==200 and wall.json()['results'][0]['allowed']
    assert not http.post('/api/client-matter-validations',json={'clientId':'12345','matterId':'789012'},headers=headers).json()['valid']
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['root'],matter_id=m));db.commit()
    result=http.post('/api/client-matter-validations',json={'clientId':'012345','matterId':'789012'},headers=headers).json()
    assert not result['valid'] and 'clientName' not in result
