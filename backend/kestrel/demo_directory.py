"""Trusted local-operator identity rename and explicit demo credential export."""
from sqlalchemy import select,update
from kestrel.demo_names import NAMED,DOMAINS,username
from kestrel.demo_setup import PROFILES
from kestrel.models import Account,Organization,Role,RoleGrant,ServerSession
from kestrel.services.auth import HASHER,audit

def rename_accounts(db,previous_settings):
    mappings=[(f"{p['prefix']}{i:02}@kestrel.example",username(p,i),p['org']) for p in PROFILES for i in range(1,4)]
    mappings.extend((previous_settings[key].casefold(),target,'firm') for key,target in NAMED.items() if previous_settings.get(key))
    pending=[]
    for old,target,org in mappings:
        source=db.scalar(select(Account).where(Account.username==old))
        destination=db.scalar(select(Account).where(Account.username==target))
        if source and destination and source.id!=destination.id:raise ValueError('Target UPN already belongs to another account')
        if not source:continue
        if db.get(Organization,source.organization_id).code!=org:raise ValueError('Employer mismatch; refusing identity migration')
        if source.username!=target or source.email!=target:pending.append((source,target))
    for account,target in pending:
        account.username=target;account.email=target
        db.execute(update(ServerSession).where(ServerSession.account_id==account.id).values(revoked=True))
        audit(db,'account.rename','allowed',account.id)
    db.flush()
    return len(pending)

def credential_rows(db,settings):
    password=settings['KESTREL_DUMMY_PASSWORD']
    if password!=settings['KESTREL_INTERVIEW_PASSWORD']:raise ValueError('Configured demo passwords differ')
    employers={'firm':'Freshfields','halden':'Halden Industries','castlegate':'Castlegate'}
    named={NAMED['KESTREL_CHRIS_EMAIL']:'Chris Madden',NAMED['KESTREL_SUMEET_EMAIL']:'Sumeet Josh',NAMED['KESTREL_RAMI_EMAIL']:'Rami Jaloudi'}
    rows=[]
    for account,org in db.execute(select(Account,Organization.code).join(Organization,Organization.id==Account.organization_id).order_by(Account.username)):
        if org not in DOMAINS or not account.username.endswith('@'+DOMAINS[org]) or account.email!=account.username:
            raise ValueError('Account employer/UPN is not a configured fictional identity')
        if not account.password_customized:HASHER.verify(account.password_hash,password)
        roles=list(db.scalars(select(Role.name).join(RoleGrant,RoleGrant.role_id==Role.id).where(RoleGrant.account_id==account.id).order_by(Role.name)))
        host='admin.localhost' if org=='firm' and 'root_admin' in roles else {'firm':'firm.localhost','halden':'client.localhost','castlegate':'bank.localhost'}[org]
        display=named.get(account.username,account.username.split('@')[0])
        rows.append({'DisplayName':display,'Employer':employers[org],'UPN':account.username,'Email':account.email,
            'Password':'' if account.password_customized else password,'Roles':'; '.join(roles),'PortalURL':f'https://{host}:8443/portal','Active':'Yes' if account.active else 'No'})
    return rows
