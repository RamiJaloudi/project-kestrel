from fastapi.testclient import TestClient
from kestrel.main import create_app
from kestrel.preview import GROUPS


def test_portals_swagger_and_group_schemas():
    for host in ['localhost', 'admin.localhost', 'firm.localhost', 'client.localhost', 'bank.localhost']:
        with TestClient(create_app(), base_url=f'https://{host}') as client:
            assert client.get('/').status_code == 200
            assert client.get('/portal').status_code == 200
            assert client.get('/preview').status_code == 200
            assert not client.cookies
            docs = client.get('/docs')
            assert docs.status_code == 200
            assert '/swagger/swagger-ui-bundle.js' in docs.text
            assert '/swagger-session.js' in docs.text
            assert 'requestInterceptor: window.kestrelSwaggerRequest' in docs.text
            assert 'cdn.jsdelivr.net' not in docs.text
            assert 'Unofficial synthetic candidate demonstration' not in docs.text
            assert client.get('/swagger/swagger-ui-bundle.js').status_code == 200
            assert client.get('/swagger-session.js').status_code == 200
            for group, prefix in GROUPS.items():
                assert client.get('/docs/'+group).status_code == 200
                schema = client.get(f'/openapi/{group}.json').json()
                assert schema['paths'] and all(p.startswith(prefix) for p in schema['paths'])
            assert client.get('/docs/missing').status_code == 404
            assert client.get('/openapi/missing.json').status_code == 404
            assert client.get('/api/v1/auth/me').status_code == 401


def test_http_preview_is_read_only():
    with TestClient(create_app(), base_url='http://localhost') as client:
        assert client.get('/').status_code == 200
        assert client.get('/docs').status_code == 200
        assert client.post('/api/v1/auth/login', json={'username':'x','password':'y'}).status_code == 403
        assert client.get('/api/v1/auth/me', headers={'cookie':'__Host-kestrel_session=forged'}).status_code == 403
