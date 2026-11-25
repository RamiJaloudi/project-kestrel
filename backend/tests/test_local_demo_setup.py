import json
from pathlib import Path
from sqlalchemy import select,func
from test_auth_policy import env
from kestrel.localenv import read_env
from kestrel.interview_setup import setup
from kestrel.models import Account,Role,RoleGrant,MatterAssignment
from kestrel.services.auth import HASHER


def test_literal_env_preserves_password_and_executes_nothing(tmp_path):
    file=tmp_path/'.env'
    secret='test-only-$()`value=kept#literal'
    file.write_text('KESTREL_INTERVIEW_PASSWORD='+json.dumps(secret)+'\n')
    assert read_env(file)['KESTREL_INTERVIEW_PASSWORD']==secret


def test_requested_accounts_shared_password_distinct_roles_and_idempotence(env,tmp_path):
    _,sessions,_,_=env
    values={'KESTREL_INTERVIEW_PASSWORD':'isolated-synthetic-test-password-32',
      'KESTREL_CHRIS_EMAIL':'Chris.MADDEN@freshfields.com.fictonal',
      'KESTREL_SUMEET_EMAIL':'Sumeet.Josh_external@freshfields.com.fictional'}
    marker=tmp_path/'fixture.json'
    with sessions() as db:
        accounts=setup(db,values,marker)
        first=[a.id for a in accounts]
        assert accounts[0].password_hash!=accounts[1].password_hash
        for account in accounts:assert HASHER.verify(account.password_hash,values['KESTREL_INTERVIEW_PASSWORD'])
        assert set(db.scalars(select(Role.name).join(RoleGrant,RoleGrant.role_id==Role.id).where(RoleGrant.account_id==accounts[0].id)))=={'legal_sme'}
        assert set(db.scalars(select(Role.name).join(RoleGrant,RoleGrant.role_id==Role.id).where(RoleGrant.account_id==accounts[1].id)))=={'root_admin'}
        assert [a.id for a in setup(db,values,marker)]==first
        matter=json.loads(marker.read_text())['matter_id']
        assert db.scalar(select(func.count()).select_from(MatterAssignment).where(MatterAssignment.matter_id==matter))==2
