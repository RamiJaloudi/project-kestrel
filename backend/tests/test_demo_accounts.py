import pytest
from sqlalchemy import select,func
from test_auth_policy import env,login
from fastapi.testclient import TestClient
from kestrel.demo_setup import setup,PROFILES,setup_owner
from kestrel.demo_names import username as profile_username,NAMED
from kestrel.models import Account,Role,RoleGrant,MatterAssignment,CleanTeamMembership
from kestrel.services.auth import HASHER
from kestrel.repositories.identity import principal,clean_scope
from reference_policy import allowed
from kestrel.services.auth import clock

PASSWORD='isolated-dummy-account-test-password'

def test_three_per_role_and_clean_team_idempotent_scoped_accounts(env):
    _,sessions,_,app=env
    with sessions() as db:
        rows=setup(db,PASSWORD)
        assert len(rows)==33 and len(PROFILES)==11
        ids={r['username']:r['id'] for r in rows}
        matter=rows[0]['matter_id']
        for row in rows:
            account=db.get(Account,row['id'])
            assert HASHER.verify(account.password_hash,PASSWORD)
            roles=set(db.scalars(select(Role.name).join(RoleGrant,RoleGrant.role_id==Role.id).where(RoleGrant.account_id==account.id)))
            assert roles=={row['role']}
            assert (clean_scope(db,account.id,matter,'pricing',clock()))==row['clean_team']
        root=db.get(Account,ids['admin01@freshfields.example'])
        assert not allowed(db,principal(db,root,clock()),action='read_source',matter=matter,now=clock())
        assignment=db.scalar(select(MatterAssignment).where(MatterAssignment.account_id==root.id,MatterAssignment.matter_id==matter))
        assignment.revoked=True;db.commit()
        assert {r['username']:r['id'] for r in setup(db,PASSWORD)}==ids
        assert db.get(MatterAssignment,assignment.id).revoked
        assert db.scalar(select(func.count()).select_from(MatterAssignment).where(MatterAssignment.matter_id==matter))==33
    # Representative account from every profile authenticates with server-enforced role/org.
    for profile in PROFILES:
        host=profile['host']
        with TestClient(app,base_url='https://'+host) as client:
            result=client.post('/api/v1/auth/login',json={'username':profile_username(profile,1),'password':PASSWORD},headers={'origin':'https://'+host})
            assert result.status_code==200
            assert client.get('/api/v1/auth/me').json()['roles']==[profile['role']]

def test_setup_never_resets_changed_password_or_restores_disabled_user(env):
    _,sessions,_,_=env
    with sessions() as db:
        rows=setup(db,PASSWORD)
        account=db.get(Account,rows[0]['id']);account.active=False;db.commit()
        setup(db,PASSWORD)
        assert not account.active
        with pytest.raises(ValueError):setup(db,'different-operator-requested-password')


def test_employer_upn_migration_preserves_identity_grants_and_session_revocation(env):
    from kestrel.demo_directory import rename_accounts
    from kestrel.models import ServerSession
    from kestrel.services.auth import digest
    _,sessions,_,_=env
    with sessions() as db:
        rows=setup(db,PASSWORD)
        original={r['id'] for r in rows}
        target=rows[0]
        account=db.get(Account,target['id'])
        account.username='admin01@kestrel.example';account.email=account.username
        session=ServerSession(account_id=account.id,token_hash=digest('test-token'),csrf_hash=digest('test-csrf'),host='admin.localhost',expires_at=clock()+500)
        db.add(session);db.commit()
        grant_ids=set(db.scalars(select(MatterAssignment.id).where(MatterAssignment.account_id==account.id)))
        assert rename_accounts(db,{})==1;db.commit()
        assert account.username=='admin01@freshfields.example' and session.revoked
        assert grant_ids==set(db.scalars(select(MatterAssignment.id).where(MatterAssignment.account_id==account.id)))
        assert {r['id'] for r in setup(db,PASSWORD)}==original
        assert rename_accounts(db,{})==0


def test_owner_setup_is_scoped_idempotent_and_has_no_sme_or_clean_team_role(env):
    _,sessions,_,_=env
    with sessions() as db:
        rows=setup(db,PASSWORD)
        owner=setup_owner(db,PASSWORD,NAMED['KESTREL_RAMI_EMAIL'])
        owner_id=owner.id
        assert setup_owner(db,PASSWORD,NAMED['KESTREL_RAMI_EMAIL']).id==owner_id
        actor=principal(db,owner,clock())
        assert {r.value for r in actor.roles}=={'root_admin'}
        assert rows[0]['matter_id'] in actor.matters
        assert not clean_scope(db,owner.id,rows[0]['matter_id'],'pricing',clock())
        assignment=db.scalar(select(MatterAssignment).where(MatterAssignment.account_id==owner_id))
        assignment.revoked=True;db.commit()
        setup_owner(db,PASSWORD,NAMED['KESTREL_RAMI_EMAIL'])
        assert db.get(MatterAssignment,assignment.id).revoked
