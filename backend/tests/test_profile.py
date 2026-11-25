from fastapi.testclient import TestClient
from test_auth_policy import env, login, PASSWORD
from kestrel.models import Account, CleanTeamMembership, EthicalWall
from kestrel.services import auth


def test_profile_identity_and_administrator_metadata(env):
    http, sessions, ids, app = env
    login(http)
    profile = http.get('/api/v1/auth/profile').json()
    assert profile['upn'] == 'lawyer' and profile['employee_id']
    assert 'password' not in str(profile) and 'token' not in str(profile)
    assert http.get('/api/v1/admin/accounts').status_code == 403
    with TestClient(app, base_url='https://firm.localhost') as root:
        csrf = login(root, 'root').json()['csrf_token']
        headers = {'origin':'https://firm.localhost','x-csrf-token':csrf}
        records = root.get('/api/v1/admin/accounts').json()
        row = next(r for r in records if r['id'] == ids['lawyer'])
        body = {'display_name':'Test Lawyer','employee_id':'000012','expected_revision':row['revision']}
        assert root.patch('/api/v1/admin/accounts/'+row['id'],json=body,headers=headers).status_code == 200
        assert root.patch('/api/v1/admin/accounts/'+row['id'],json=body,headers=headers).status_code == 409
        body['expected_revision'] += 1
        assert root.patch('/api/v1/admin/accounts/'+row['id'],json={**body,'roles':['root_admin']},headers=headers).status_code == 422
        other = next(r for r in records if r['id'] == ids['sme'])
        assert root.patch('/api/v1/admin/accounts/'+other['id'],json={**body,'expected_revision':other['revision']},headers=headers).status_code == 409
    assert http.get('/api/v1/auth/profile').json()['employee_id'] == '000012'
    assert http.patch('/api/v1/admin/accounts/'+ids['lawyer'],json=body).status_code == 403


def test_password_rotation_revokes_other_sessions_and_preserves_current(env):
    http, sessions, ids, app = env
    csrf = login(http).json()['csrf_token']
    old = http.cookies.get(auth.COOKIE)
    with TestClient(app,base_url='https://firm.localhost') as other:
        login(other)
        headers={'origin':'https://firm.localhost','x-csrf-token':csrf}
        body={'current_password':PASSWORD,'new_password':'changed-profile-test-password','confirm_password':'changed-profile-test-password'}
        assert http.post('/api/v1/auth/password',json=body).status_code == 403
        assert http.post('/api/v1/auth/password',json={**body,'current_password':'incorrect'},headers=headers).status_code == 400
        assert http.post('/api/v1/auth/password',json={**body,'confirm_password':'different-passphrase'},headers=headers).status_code == 400
        result=http.post('/api/v1/auth/password',json=body,headers=headers)
        assert result.status_code == 200
        assert result.json()['csrf_token'] != csrf and http.cookies.get(auth.COOKIE) != old
        assert http.get('/api/v1/auth/profile').status_code == 200
        assert other.get('/api/v1/auth/profile').status_code == 401
        other.cookies.clear()
        other.cookies.set(auth.COOKIE,old,domain='firm.localhost',path='/')
        assert other.get('/api/v1/auth/profile').status_code == 401
        assert login(other).status_code == 401
        assert other.post('/api/v1/auth/login',json={'username':'lawyer','password':body['new_password']},headers={'origin':'https://firm.localhost'}).status_code == 200
    with sessions() as db:
        assert db.get(Account,ids['lawyer']).password_customized


def test_wrong_current_password_throttle_and_logout_all(env):
    http,_,_,app=env
    csrf=login(http).json()['csrf_token']
    headers={'origin':'https://firm.localhost','x-csrf-token':csrf}
    body={'current_password':'wrong','new_password':'a-new-test-password','confirm_password':'a-new-test-password'}
    for _ in range(5):assert http.post('/api/v1/auth/password',json=body,headers=headers).status_code==400
    assert http.post('/api/v1/auth/password',json=body,headers=headers).status_code==429
    with TestClient(app,base_url='https://firm.localhost') as other:
        login(other)
        assert http.post('/api/v1/auth/logout-all',headers=headers).status_code==204
        assert other.get('/api/v1/auth/profile').status_code==401
        assert http.get('/api/v1/auth/profile').status_code==401


def test_custom_password_survives_setup_and_is_not_exported(env,tmp_path):
    from kestrel.demo_setup import setup,setup_owner,reset
    from kestrel.demo_names import NAMED
    from kestrel.demo_directory import credential_rows
    from kestrel.interview_setup import setup as interview
    _,sessions,_,_=env
    with sessions() as db:
        records=setup(db,PASSWORD)
        owner=setup_owner(db,PASSWORD,NAMED['KESTREL_RAMI_EMAIL'])
        values={**NAMED,'KESTREL_DUMMY_PASSWORD':PASSWORD,'KESTREL_INTERVIEW_PASSWORD':PASSWORD}
        interview(db,values,tmp_path/"interview.json")
        usernames=[r['username'] for r in records]+list(NAMED.values())
        from sqlalchemy import select
        for account in db.scalars(select(Account).where(Account.username.in_(usernames))):
            account.password_hash=auth.HASHER.hash('changed-test-password');account.password_customized=True
        db.commit()
        setup(db,PASSWORD);setup_owner(db,PASSWORD,owner.username);interview(db,values,tmp_path/"interview.json")
        # fixture-only accounts have employer-qualified UPNs; the env also has unqualified test accounts.
        from kestrel.models import Organization
        from kestrel.demo_names import DOMAINS
        for account in db.scalars(select(Account).where(~Account.username.in_(usernames))):
            account.username=account.username+'-fixture@'+DOMAINS[db.get(Organization,account.organization_id).code];account.email=account.username
        db.commit()
        exported={r['UPN']:r['Password'] for r in credential_rows(db,values)}
        assert all(exported[u]=='' for u in usernames)
        reset(db,owner,PASSWORD);db.commit()
        assert not owner.password_customized and auth.HASHER.verify(owner.password_hash,PASSWORD)


def test_profile_hides_inactive_and_walled_clean_team_scopes(env):
    http,sessions,ids,_=env
    with sessions() as db:
        db.add(CleanTeamMembership(account_id=ids['lawyer'],matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=auth.clock()+1000))
        db.commit()
    login(http)
    assert len(http.get('/api/v1/auth/profile').json()['clean_team_scopes']) == 1
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter'],active=True));db.commit()
    assert http.get('/api/v1/auth/profile').json()['clean_team_scopes'] == []
