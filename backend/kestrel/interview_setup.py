"""Explicitly requested fictional demo accounts, provisioned by the local operator."""
import json
import os
from pathlib import Path
from sqlalchemy import select
from argon2.exceptions import VerificationError
from kestrel.localenv import load_env,ROOT
from kestrel.database import make_engine,database_url,factory
from kestrel.bootstrap import provision
from kestrel.models import Account,Role,RoleGrant,Client,Matter,MatterValidation,MatterAssignment
from kestrel.services.auth import HASHER,clock,audit


def setup(db,values,fixture_file):
    password=values['KESTREL_INTERVIEW_PASSWORD']
    if len(password)<15:raise ValueError('Demo password must contain at least 15 characters')
    accounts=[]
    for key,role in [('KESTREL_CHRIS_EMAIL','legal_sme'),('KESTREL_SUMEET_EMAIL','root_admin')]:
        name=values[key].strip().casefold()
        account=db.scalar(select(Account).where(Account.username==name))
        if account is None:account=provision(db,name,'firm',[role],password,name)
        else:
            roles=set(db.scalars(select(Role.name).join(RoleGrant,RoleGrant.role_id==Role.id).where(RoleGrant.account_id==account.id)))
            if roles!={role}:raise ValueError('Existing interview account role differs; explicit operator review required')
            try:
                if not account.password_customized:HASHER.verify(account.password_hash,password)
            except VerificationError:raise ValueError('Existing interview password differs; explicit reset required')
        accounts.append(account)
    if not fixture_file.exists():
        client=Client(name='Interview synthetic client',created_by=accounts[1].id);db.add(client);db.flush()
        matter=Matter(name='Interview demonstration — Project Skylark');db.add(matter);db.flush()
        db.add(MatterValidation(matter_id=matter.id,client_id=client.id,status='validated'))
        for account in accounts:
            db.add(MatterAssignment(account_id=account.id,matter_id=matter.id,expires_at=clock()+30*86400))
        audit(db,'interview.fixture','created',accounts[1].id,matter_id=matter.id)
        db.commit()
        fixture_file.write_text(json.dumps({'matter_id':matter.id,'client_id':client.id}),encoding='utf-8')
    return accounts


if __name__=='__main__':
    load_env()
    if os.environ.get('KESTREL_PROVISION_INTERVIEW_ACCOUNTS')!='true':
        print('Interview provisioning disabled.')
    else:
        with factory(make_engine(database_url()))() as db:
            setup(db,os.environ,ROOT/'.runtime/interview-fixture.json')
        print('Fictional Legal SME and Admin accounts verified; shared password remains in private .env.')
