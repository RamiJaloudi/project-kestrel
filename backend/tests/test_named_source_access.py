import pytest
from pathlib import Path
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_auth_policy import env,login
from test_document_workflow import candidate,BASE
from test_observability_governance import post
from kestrel.models import Role,RoleGrant,CleanTeamMembership,EthicalWall
from kestrel.services.auth import clock
G='/api/v1/source-access'

def setup(env):
    http,sessions,ids,_=env
    with sessions() as db:
        role=Role(name='antitrust_counsel');db.add(role);db.flush();db.add(RoleGrant(account_id=ids['sme'],role_id=role.id))
        for person in ['lawyer','sme']:db.add(CleanTeamMembership(account_id=ids[person],matter_id=ids['matter'],scope='pricing',approved_by=ids['root'],expires_at=clock()+3600))
        db.commit()
    source,finding,csrf=candidate(env,'clean_team')
    return source,finding,csrf

def test_named_halden_source_requires_review_independent_approval_and_live_membership(env):
    http,sessions,ids,app=env;source,_,csrf=setup(env)
    proposal={'source_id':source['id'],'username':'client','outside_business':True,'expires_in_days':7,'rationale':'Verified fictional named recipient is outside the business.'}
    assert post(http,G,csrf,proposal).status_code==409
    assert post(http,'/api/v1/diligence/documents/'+source['id']+'/reviews',csrf,{'expected_revision':0,'title':'Synthetic reviewed pricing agreement','counterparty':'Fictional counterparty','scope':'financial','coverage_state':'complete','rationale':'All source passages and candidates checked by lawyer'}).status_code==201
    proposed=post(http,G,csrf,proposal);assert proposed.status_code==201,proposed.text
    grant=proposed.json()
    with TestClient(app,base_url='https://client.localhost') as client:
        login(client,'client',origin='https://client.localhost')
        assert client.get(BASE+'/documents/'+source['id']+'/reader').status_code==403
        assert post(http,G+'/'+grant['id']+'/approve',csrf,{'rationale':'Attempted self approval'}).status_code==403
        csrf=login(http,'sme').json()['csrf_token']
        assert post(http,G+'/'+grant['id']+'/approve',csrf,{'rationale':'Independent antitrust approval of exact source and recipient'}).status_code==200
        assert client.get(BASE+'/documents/'+source['id']+'/reader').status_code==200
        assert client.get(BASE+'/documents/'+source['id']+'/download').status_code==200
        assert client.get(BASE+'/findings',params={'matter_id':ids['matter']}).status_code==403
        with TestClient(app,base_url='https://bank.localhost') as bank:
            login(bank,'bank',origin='https://bank.localhost');assert bank.get(BASE+'/documents/'+source['id']+'/reader').status_code==403
        with sessions() as db:
            membership=db.scalar(select(CleanTeamMembership).where(CleanTeamMembership.account_id==ids['client']));membership.revoked=True;db.commit()
        assert client.get(BASE+'/documents/'+source['id']+'/reader').status_code==403
    revoked=post(http,G+'/'+grant['id']+'/revoke',csrf,{'rationale':'Explicit revocation retained for the audit record'})
    assert revoked.status_code==200 and revoked.json()['decision_rationale']=='Independent antitrust approval of exact source and recipient'
    assert revoked.json()['revocation_rationale']=='Explicit revocation retained for the audit record' and revoked.json()['revoked_by']==ids['sme']
    # The 0026 retention barrier may stop first; neither record family may be dropped.
    with pytest.raises(RuntimeError,match='Retained grant revocation evidence|Retained document identity/import'):
        command.downgrade(Config(str(Path(__file__).resolve().parents[1]/'alembic.ini')),'0017')
    # Empty later migrations may roll back before the older evidence guard.
    # Restore the test schema to the application's head before testing routes.
    command.upgrade(Config(str(Path(__file__).resolve().parents[1]/'alembic.ini')),'head')
    login(http,'root');assert http.get(BASE+'/documents/'+source['id']+'/reader').status_code==403

