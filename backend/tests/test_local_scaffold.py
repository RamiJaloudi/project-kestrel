from fastapi.testclient import TestClient
from kestrel.main import app

def test_local_health_only():
    client=TestClient(app)
    data=client.get('/health').json()
    assert data['status']=='ok'
    assert data['protected_endpoints']=='deny-by-default'

def test_protected_routes_deny_by_default():
    c=TestClient(app)
    paths=['/api/v1/auth/me','/api/v1/admin/playbooks','/api/v1/governance/inbox']
    assert all(c.get(p).status_code==401 for p in paths)
    assert c.post('/api/v1/governance/reanalysis/R-001/approve').status_code==401

def test_legacy_identity_header_cannot_bypass():
    c=TestClient(app)
    h={'X-Demo-User':'root_admin','X-Role':'legal_sme'}
    assert c.get('/api/v1/governance/inbox',headers=h).status_code==401
