import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from test_auth_policy import env,login,PASSWORD
from kestrel.models import ServerSession,Account,EthicalWall
from kestrel.services import auth

ORIGIN={'origin':'https://firm.localhost'}

def restore(http,headers=None):return http.post('/api/v1/auth/session',headers=ORIGIN if headers is None else headers)

def test_remembered_cookie_expiry_and_username_preference(env):
    http,sessions,ids,_=env
    result=login(http,remember_me=True)
    assert result.status_code==200 and result.json()['expires_in']==30*86400
    cookies=result.headers.get_list('set-cookie')
    assert len(cookies)==2
    for cookie in cookies:
        assert all(flag in cookie for flag in ['Secure','HttpOnly','SameSite=strict','Path=/','Max-Age=2592000'])
        assert 'Domain=' not in cookie and PASSWORD not in cookie
    assert http.get('/api/v1/auth/preferences').json()=={'username':'lawyer','remember_me':True}
    with sessions() as db:
        row=db.scalar(select(ServerSession))
        assert 30*86400-5<=row.expires_at-auth.clock()<=30*86400
        assert row.token_hash==auth.digest(http.cookies.get(auth.COOKIE))
    assert login(http,remember_me='yes').status_code==422

def test_normal_session_does_not_persist_and_forget_preference(env):
    http,_,_,_=env
    login(http,remember_me=True)
    result=login(http,remember_me=False)
    cookie=next(c for c in result.headers.get_list('set-cookie') if c.startswith(auth.COOKIE+'='))
    assert 'Max-Age' not in cookie and 'expires=' not in cookie.lower()
    assert result.json()['expires_in']==1800
    assert http.get('/api/v1/auth/preferences').json()['username']==''
    login(http,remember_me=True)
    assert http.delete('/api/v1/auth/preferences').status_code==403
    assert http.delete('/api/v1/auth/preferences',headers=ORIGIN).status_code==204
    assert http.get('/api/v1/auth/preferences').json()['username']==''
    # Forgetting a name is separate from ending the authenticated session.
    assert http.get('/api/v1/auth/me').status_code==200

def test_restored_session_works_across_pages_and_logout_revokes(env):
    http,sessions,ids,app=env
    result=login(http,remember_me=True)
    token=http.cookies.get(auth.COOKIE)
    with TestClient(app,base_url='https://firm.localhost') as reopened:
        reopened.cookies.set(auth.COOKIE,token,domain='firm.localhost',path='/')
        first=restore(reopened);second=restore(http)
        assert first.status_code==200 and first.json()['identity']['id']==ids['lawyer']
        assert first.json()['csrf_token']==second.json()['csrf_token']==result.json()['csrf_token']
        assert not first.headers.get_list('set-cookie')  # No hidden sliding expiry.
        assert reopened.post('/api/v1/auth/logout',headers={**ORIGIN,'x-csrf-token':first.json()['csrf_token']}).status_code==204
    assert restore(http).status_code==401

def test_restore_requires_origin_and_host_and_keeps_live_policy(env):
    http,sessions,ids,_=env
    login(http,remember_me=True)
    assert restore(http,{}).status_code==403
    assert restore(http,{'origin':'https://evil.example'}).status_code==403
    cookie=http.cookies.get(auth.COOKIE)
    wrong=http.post('https://client.localhost/api/v1/auth/session',headers={'origin':'https://client.localhost','cookie':auth.COOKIE+'='+cookie})
    assert wrong.status_code==403
    with sessions() as db:
        db.add(EthicalWall(account_id=ids['lawyer'],matter_id=ids['matter']));db.commit()
    assert restore(http).status_code==200
    assert http.get('/test/source/'+ids['matter']).status_code==403
    with sessions() as db:
        db.get(Account,ids['lawyer']).active=False;db.commit()
    assert restore(http).status_code==401

def test_restore_legacy_csrf_once_and_expired_cookie_denied(env):
    http,sessions,_,_=env
    login(http,remember_me=True)
    with sessions() as db:
        row=db.scalar(select(ServerSession));row.csrf_hash=auth.digest('legacy-random-csrf');db.commit()
    first=restore(http);assert first.status_code==200
    assert restore(http).json()['csrf_token']==first.json()['csrf_token']
    with sessions() as db:
        db.scalar(select(ServerSession)).expires_at=auth.clock()-1;db.commit()
    assert restore(http).status_code==401

def test_username_cookie_cannot_authenticate_or_cross_portals(env):
    http,_,_,app=env
    http.cookies.set(auth.USERNAME_COOKIE,'root',domain='firm.localhost',path='/')
    assert http.get('/api/v1/auth/me').status_code==401
    assert restore(http).status_code==401
    assert http.get('/api/v1/auth/preferences',headers={'origin':'https://evil.example'}).status_code==403
    with TestClient(app,base_url='https://bank.localhost') as bank:
        assert bank.get('/api/v1/auth/preferences').json()['username']==''
