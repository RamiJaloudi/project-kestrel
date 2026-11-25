from test_auth_policy import env, login
from kestrel.models import EthicalWall, MatterValidation, Account
from kestrel.repositories.identity import principal
from kestrel.services.auth import clock


def post(http, path, csrf, payload):
    return http.post('/api/v1/validation'+path, json=payload,
        headers={'origin':'https://firm.localhost','x-csrf-token':csrf})


def test_registry_create_validate_assign_and_wall(env):
    http, sessions, ids, app = env
    csrf = login(http,'root').json()['csrf_token']
    c = post(http,'/clients',csrf,{'name':'Synthetic Meridian'}); assert c.status_code == 201
    m = post(http,'/matters',csrf,{'name':'Synthetic Skylark','client_id':c.json()['id']}); assert m.status_code == 201
    matter=m.json()['id']
    view=http.get('/api/v1/validation/matters').json()
    assert any(r['matter_id']==matter and r['validation_status']=='pending' for r in view)
    assert post(http,f'/matters/{matter}/decision',csrf,{'status':'validated','expected_revision':1,'rationale':'Synthetic checks completed'}).status_code==200
    body={'username':'lawyer','assigned':True,'blocked':False,'days':30,'expected_revision':2,'rationale':'Approved named team member'}
    assert post(http,f'/matters/{matter}/access',csrf,body).status_code==200
    with sessions() as db:
        assert matter in principal(db,db.get(Account,ids['lawyer']),clock()).matters
    body.update(expected_revision=3,blocked=True)
    assert post(http,f'/matters/{matter}/access',csrf,body).status_code==403
    # Existing external-registry wall simulated by test fixture, not a Root Admin API bypass.
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['lawyer'],matter_id=matter));db.commit()
    rows=http.get(f'/api/v1/validation/matters/{matter}/access').json()
    assert any(r['username']=='lawyer' and r['assigned']==1 and r['blocked']==1 for r in rows)
    with sessions() as db:
        assert matter in principal(db,db.get(Account,ids['lawyer']),clock()).walls
    assert len(http.get(f'/api/v1/validation/matters/{matter}/history').json())==3
    body['expected_revision']=2
    assert post(http,f'/matters/{matter}/access',csrf,body).status_code==409
    body.update(username='root',expected_revision=3)
    assert post(http,f'/matters/{matter}/access',csrf,body).status_code==403


def test_nonadmin_wrong_matter_and_walled_admin(env):
    http,sessions,ids,_=env
    assert http.get('/api/v1/validation/matters').status_code==401
    login(http,'lawyer')
    assert http.get('/api/v1/validation/matters').status_code==403
    csrf=login(http,'root').json()['csrf_token']
    assert http.get(f"/api/v1/validation/matters/{ids['other']}/access").status_code==403
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['root'],matter_id=ids['matter']));db.commit()
    assert http.get('/api/v1/validation/matters').json()==[]
    assert http.get(f"/api/v1/validation/matters/{ids['matter']}/access").status_code==403
    body={'username':'root','assigned':True,'blocked':False,'days':30,'expected_revision':1,'rationale':'Attempting own wall removal'}
    assert post(http,f"/matters/{ids['matter']}/access",csrf,body).status_code==403


def test_validation_revokes_existing_session_matter_access(env):
    http,sessions,ids,_=env
    login(http)
    path=f"/test/source/{ids['matter']}"
    assert http.get(path).status_code==200
    with sessions() as db:
        db.get(MatterValidation,ids['matter']).status='rejected';db.commit()
    assert http.get(path).status_code==403


def test_admin_decision_csrf_and_blank_rationale(env):
    http,_,ids,_=env
    csrf=login(http,'root').json()['csrf_token']
    path=f"/matters/{ids['matter']}/decision"
    body={'status':'validated','expected_revision':1,'rationale':'   '}
    assert post(http,path,csrf,body).status_code==422
    body['rationale']='Synthetic validation rationale'
    assert post(http,path,'bad',body).status_code==403


def test_missing_validation_is_default_deny(env):
    from sqlalchemy import delete
    http,sessions,ids,_=env
    login(http)
    with sessions() as db:
        db.execute(delete(MatterValidation).where(MatterValidation.matter_id==ids['matter']));db.commit()
    assert http.get(f"/test/source/{ids['matter']}").status_code==403
