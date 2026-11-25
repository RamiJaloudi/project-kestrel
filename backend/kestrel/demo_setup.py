"""Explicit local operator fixture; real accounts, no role-switch bypass."""
import argparse
import json
import os
from pathlib import Path
from sqlalchemy import select,update
from argon2.exceptions import VerificationError
from kestrel.bootstrap import provision
from kestrel.database import make_engine,database_url,factory
from kestrel.localenv import load_env,ROOT
from kestrel.models import (Account,Organization,Role,RoleGrant,Client,Matter,MatterValidation,
    MatterAssignment,CleanTeamMembership,ServerSession)
from kestrel.services.auth import HASHER,clock,audit
from kestrel.demo_names import username as profile_username,NAMED

PROFILES=[
 {'prefix':'admin','role':'root_admin','org':'firm','host':'admin.localhost','clean_team':False},
 {'prefix':'lawyer','role':'firm_lawyer','org':'firm','host':'firm.localhost','clean_team':False},
 {'prefix':'sme','role':'legal_sme','org':'firm','host':'firm.localhost','clean_team':False},
 {'prefix':'antitrust','role':'antitrust_counsel','org':'firm','host':'firm.localhost','clean_team':True},
 {'prefix':'client','role':'client_user','org':'halden','host':'client.localhost','clean_team':False},
 {'prefix':'bank','role':'bank_analyst','org':'castlegate','host':'bank.localhost','clean_team':False},
 {'prefix':'auditor','role':'matter_auditor','org':'firm','host':'firm.localhost','clean_team':False},
 {'prefix':'cleanauditor','role':'clean_team_auditor','org':'firm','host':'firm.localhost','clean_team':True},
 {'prefix':'security','role':'security_approver','org':'firm','host':'firm.localhost','clean_team':False},
 {'prefix':'conflicts','role':'conflicts_approver','org':'firm','host':'firm.localhost','clean_team':False},
 {'prefix':'cleanteam','role':'firm_lawyer','org':'firm','host':'firm.localhost','clean_team':True}]

def reset(db,account,password):
    account.password_hash=HASHER.hash(password)
    account.password_customized=False
    db.execute(update(ServerSession).where(ServerSession.account_id==account.id).values(revoked=True))
    audit(db,'account.reset','allowed',account.id)

def setup(db,password,reset_passwords=False):
    if not 15<=len(password)<=256:raise ValueError('Demo password must contain 15–256 characters')
    rows=[]
    for profile in PROFILES:
        for index in range(1,4):
            username=profile_username(profile,index)
            account=db.scalar(select(Account).where(Account.username==username))
            if account is None:account=provision(db,username,profile['org'],[profile['role']],password,username)
            else:
                roles=set(db.scalars(select(Role.name).join(RoleGrant,RoleGrant.role_id==Role.id).where(RoleGrant.account_id==account.id)))
                if roles!={profile['role']} or db.get(Organization,account.organization_id).code!=profile['org'] or account.email!=username:
                    raise ValueError('Existing dummy account scope differs; explicit operator review required')
                try:
                    if not account.password_customized:HASHER.verify(account.password_hash,password)
                    elif reset_passwords:reset(db,account,password)
                except VerificationError:
                    if not reset_passwords:raise ValueError('Existing dummy password differs; use explicit reset-passwords')
                    reset(db,account,password)
            rows.append({**profile,'username':username,'id':account.id})
    root=rows[0]['id']
    client=db.scalar(select(Client).where(Client.client_number=='012345'))
    if client is None:
        client=Client(name='Synthetic role-testing client',client_number='012345',created_by=root);db.add(client);db.flush()
    if client.name!='Synthetic role-testing client' or client.created_by!=root:raise ValueError('Demo client number already owned by another fixture; operator review required')
    validation=db.scalar(select(MatterValidation).where(MatterValidation.client_id==client.id,MatterValidation.matter_number=='789012'))
    if validation is None:
        matter=Matter(name='Synthetic role testing — Project Kestrel');db.add(matter);db.flush()
        validation=MatterValidation(matter_id=matter.id,client_id=client.id,matter_number='789012',status='validated');db.add(validation)
        antitrust=next(r['id'] for r in rows if r['role']=='antitrust_counsel')
        expiry=clock()+30*86400
        for row in rows:
            db.add(MatterAssignment(account_id=row['id'],matter_id=matter.id,expires_at=expiry))
            if row['clean_team']:
                db.add(CleanTeamMembership(account_id=row['id'],matter_id=matter.id,scope='pricing',approved_by=antitrust,expires_at=expiry))
        audit(db,'dummy.fixture','created',root,matter_id=matter.id)
    # Existing revocations, walls, role changes, expiry or validation decisions are never reset.
    from kestrel.repositories.identity import clean_scope
    for row in rows:
        row.update(matter_id=validation.matter_id,client_matter_number='012345-789012',
            clean_team=clean_scope(db,row['id'],validation.matter_id,'pricing',clock()))
    db.commit();return rows

def setup_owner(db,password,email):
    name=email.strip().casefold()
    if name!=NAMED['KESTREL_RAMI_EMAIL']:raise ValueError('Unexpected local owner identity')
    account=db.scalar(select(Account).where(Account.username==name))
    if account is None:
        account=provision(db,name,'firm',['root_admin'],password,name)
        # Explicit local-operator seed, restricted to this project's two synthetic fixtures.
        for matter in db.scalars(select(Matter).where(Matter.name.in_(['Synthetic role testing — Project Kestrel','Interview demonstration — Project Skylark']))):
            db.add(MatterAssignment(account_id=account.id,matter_id=matter.id,expires_at=clock()+30*86400))
        audit(db,'owner.fixture','created',account.id)
        db.commit()
    else:
        roles=set(db.scalars(select(Role.name).join(RoleGrant,RoleGrant.role_id==Role.id).where(RoleGrant.account_id==account.id)))
        if roles!={'root_admin'} or db.get(Organization,account.organization_id).code!='firm' or account.email!=name:
            raise ValueError('Existing owner scope differs; operator review required')
        if not account.password_customized:HASHER.verify(account.password_hash,password)
    return account

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset-passwords',action='store_true')
    parser.add_argument('--include-interview',action='store_true')
    args=parser.parse_args()
    load_env()
    if os.environ.get('KESTREL_PROVISION_DUMMY_ACCOUNTS')!='true':
        print('Dummy provisioning disabled.');return
    password=os.environ['KESTREL_DUMMY_PASSWORD']
    with factory(make_engine(database_url()))() as db:
        rows=setup(db,password,args.reset_passwords)
        if os.environ.get('KESTREL_RAMI_EMAIL'):setup_owner(db,password,os.environ['KESTREL_RAMI_EMAIL'])
        if args.include_interview:
            if not args.reset_passwords:raise ValueError('Interview password changes require explicit reset-passwords')
            for key in ['KESTREL_CHRIS_EMAIL','KESTREL_SUMEET_EMAIL']:
                account=db.scalar(select(Account).where(Account.username==os.environ[key].casefold()))
                if account is None:raise ValueError('Interview account missing')
                reset(db,account,password)
            db.commit()
    manifest=ROOT/'.runtime/demo-accounts.json'
    manifest.write_text(json.dumps({'accounts':rows,'password_env_key':'KESTREL_DUMMY_PASSWORD'},indent=2),encoding='utf-8')
    print('33 dummy accounts verified; one synthetic matter and named pricing scopes. Password stays in .env.')

if __name__=='__main__':
    try:main()
    except Exception as error:
        from kestrel.diagnostics import emit
        row=emit('dummy_setup.failed',component='provisioning',exception=error)
        print('Dummy setup failed; inspect sanitized diagnostic '+row['event_id'])
        raise SystemExit(1)
