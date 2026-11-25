"""Firm-Root registry metadata. Direct management scope includes pending matters."""
from fastapi import HTTPException
from sqlalchemy import select,text,bindparam,or_,String
from kestrel import models as m
from kestrel.services import administration as admin,auth
from kestrel.repositories.identity import principal
from kestrel.schemas.registry_tables import RegistryAccessRow
from kestrel.adapters.extraction import canonical,digest

COUNT_BASIS='Current Root administration scope and historical registry participants/decision family; text filters then determine the filtered count.'


def fresh(db,request,actor_id,matter=None):
    db.expire_all();identity=auth.authenticate(db,request)
    actor=identity[2]
    if actor.id!=actor_id:raise HTTPException(403,'Identity changed during registry request')
    admin.require_admin(actor)
    if matter is not None:admin.require_matter(db,actor,matter)
    return identity


def receipt(db,identity,matter=None,username=None):
    """Only registry identity/scope/projection drivers, never source permission."""
    actor=identity[2];session=identity[1];now=auth.clock()
    areas=admin.scopes(db,actor)|({matter} if matter else set())
    clients=set(db.scalars(select(m.MatterValidation.client_id).where(m.MatterValidation.matter_id.in_(areas))))
    if matter is None:clients.update(db.scalars(select(m.Client.id).where(m.Client.created_by==actor.id)))
    subjects={actor.id}
    for model in [m.MatterAssignment,m.EthicalWall]:subjects.update(db.scalars(select(model.account_id).where(model.matter_id.in_(areas))))
    if username:
        target=db.scalar(select(m.Account.id).where(m.Account.username==username.strip().casefold()))
        if target:subjects.add(target)
    def rows(model,fields,*where):return sorted([list(row) for row in db.execute(select(*[getattr(model,key) for key in fields]).where(*where))],key=canonical)
    parts={'actor':[actor.id,actor.org.value,sorted(actor.roles),sorted(actor.walls),sorted(actor.client_walls)],
        'session':[session.id,session.account_id,session.host,session.expires_at,session.revoked,session.expires_at>now],
        'scope':sorted(areas)}
    parts['accounts']=rows(m.Account,['id','username','organization_id','active'],m.Account.id.in_(subjects))
    parts['organizations']=rows(m.Organization,['id','code'],m.Organization.id.in_(select(m.Account.organization_id).where(m.Account.id.in_(subjects))))
    parts['grants']=rows(m.RoleGrant,['id','account_id','role_id'],m.RoleGrant.account_id.in_(subjects))
    parts['roles']=rows(m.Role,['id','name'],m.Role.id.in_(select(m.RoleGrant.role_id).where(m.RoleGrant.account_id.in_(subjects))))
    assignment_fields=['id','account_id','matter_id','starts_at','expires_at','revoked']
    assignments=rows(m.MatterAssignment,assignment_fields,or_(m.MatterAssignment.matter_id.in_(areas),m.MatterAssignment.account_id==actor.id))
    parts['assignments']=[row+[row[3]<=now<row[4] and not row[5]] for row in assignments]
    parts['walls']=rows(m.EthicalWall,['id','account_id','matter_id','active'],or_(m.EthicalWall.matter_id.in_(areas),m.EthicalWall.account_id==actor.id))
    parts['validation']=rows(m.MatterValidation,['matter_id','client_id','status','revision','matter_number'],m.MatterValidation.matter_id.in_(areas))
    parts['matter']=rows(m.Matter,['id','name'],m.Matter.id.in_(areas))
    parts['clients']=rows(m.Client,['id','name','client_number','created_by'],m.Client.id.in_(clients))
    parts['published_walls']=rows(m.GovernanceVersion,['id','matter_id','definition_json'],m.GovernanceVersion.matter_id.in_(areas),m.GovernanceVersion.kind=='wall_policy',m.GovernanceVersion.state=='published')
    statement=text('SELECT id,client_id,matter_id,account_id,role_name,relationship_kind,entry_type,starts_at,expires_at FROM vw_person_wall_entries WHERE starts_at<=:now AND (expires_at IS NULL OR expires_at>:now) AND (account_id IS NULL OR account_id IN :subjects) AND (matter_id IN :matters OR (matter_id IS NULL AND client_id IN :clients))').bindparams(bindparam('subjects',expanding=True,type_=String),bindparam('matters',expanding=True,type_=String),bindparam('clients',expanding=True,type_=String))
    parts['person_walls']=sorted([list(row) for row in db.execute(statement,{'now':now,'subjects':sorted(subjects),'matters':sorted(areas),'clients':sorted(clients)})],key=canonical)
    parts['history']=rows(m.AdministrationDecision,['id','matter_id','kind','actor_id','target_id','occurred_at','revision'],m.AdministrationDecision.matter_id.in_(areas),or_(m.AdministrationDecision.kind.like('matter.%'),m.AdministrationDecision.kind.like('access.%')))
    return digest(canonical(parts).encode())


def guarded_read(db,actor,request,prepare,*,matter=None,username=None):
    try:
        identity=fresh(db,request,actor.id,matter);before=receipt(db,identity,matter,username)
        result=prepare(identity[2])
        identity=fresh(db,request,actor.id,matter)
        if receipt(db,identity,matter,username)!=before:raise HTTPException(409,'Registry authority or metadata changed; reload the current context')
        checked=prepare(identity[2])
        identity=fresh(db,request,actor.id,matter)
        if receipt(db,identity,matter,username)!=before or canonical(result)!=canonical(checked):raise HTTPException(409,'Registry authority or metadata changed; reload the current context')
        return checked
    except HTTPException:
        db.rollback();raise


def access_rows(db,actor,matter):
    source=admin.access_rows(db,actor,matter,now=auth.clock())
    active=dict(db.execute(select(m.Account.id,m.Account.active).where(m.Account.id.in_([row['account_id'] for row in source]))).all())
    return [RegistryAccessRow(**{**row,'id':row['account_id'],'active':active[row['account_id']]}).model_dump() for row in source]


def history_rows(db,actor,matter):
    admin.require_matter(db,actor,matter)
    fields=['id','matter_id','kind','rationale','actor_id','target_id','occurred_at','revision']
    return [dict(zip(fields,row)) for row in db.execute(select(*[getattr(m.AdministrationDecision,key) for key in fields]).where(
        m.AdministrationDecision.matter_id==matter,or_(m.AdministrationDecision.kind.like('matter.%'),m.AdministrationDecision.kind.like('access.%')))
        .order_by(m.AdministrationDecision.occurred_at,m.AdministrationDecision.revision,m.AdministrationDecision.id))]


def query(db,actor,request,payload,dataset):
    def prepare(current):
        validation=admin.require_matter(db,current,payload.matter_id)
        rows=access_rows(db,current,payload.matter_id) if dataset=='access' else history_rows(db,current,payload.matter_id)
        def value(item):return '' if item is None else str(item).casefold()
        needle=payload.search.casefold();columns={key:text.casefold() for key,text in payload.column_filters.items() if text}
        filtered=[row for row in rows if (not needle or any(needle in value(item) for item in row.values())) and all(text in value(row[key]) for key,text in columns.items())]
        filtered.sort(key=lambda row:row['id'])
        filtered.sort(key=lambda row:(row[payload.sort] is not None,row[payload.sort] if payload.sort in {'occurred_at','revision'} else value(row[payload.sort])),reverse=payload.direction=='desc')
        return {'draw':payload.draw,'recordsTotal':len(rows),'recordsFiltered':len(filtered),'data':filtered[payload.start:payload.start+payload.length],
            'matter_revision':validation.revision,'count_basis':COUNT_BASIS}
    return guarded_read(db,actor,request,prepare,matter=payload.matter_id)


def pinned(db,actor,matter,revision):
    validation=admin.require_matter(db,actor,matter)
    if validation.revision!=revision:raise HTTPException(409,'Registry revision changed; reload before preparing a command')
    return validation


def context_row(db,actor,matter,revision):
    pinned(db,actor,matter,revision)
    row=db.execute(text('SELECT * FROM vw_client_matter_validation WHERE matter_id=:matter'),{'matter':matter}).mappings().one_or_none()
    if row is None:raise HTTPException(403,'Matter administration denied')
    return dict(row)


def target_row(db,actor,matter,username,revision=None):
    validation=admin.require_matter(db,actor,matter) if revision is None else pinned(db,actor,matter,revision)
    account=db.scalar(select(m.Account).where(m.Account.username==username.strip().casefold()))
    if account is None:raise HTTPException(404,'Target unavailable')
    now=auth.clock()
    assigned=db.scalar(select(m.MatterAssignment.id).where(m.MatterAssignment.account_id==account.id,m.MatterAssignment.matter_id==matter,
        m.MatterAssignment.starts_at<=now,m.MatterAssignment.expires_at>now,m.MatterAssignment.revoked.is_(False)).limit(1)) is not None
    blocked=db.scalar(select(m.EthicalWall.id).where(m.EthicalWall.account_id==account.id,m.EthicalWall.matter_id==matter,m.EthicalWall.active.is_(True)).limit(1)) is not None
    return {'account_id':account.id,'username':account.username,'organization':db.get(m.Organization,account.organization_id).code,'assigned':assigned,
        'blocked':blocked,'effective_blocked':matter in principal(db,account,now).walls,'active':account.active,'matter_revision':validation.revision}


def context(db,actor,request,matter,revision):return guarded_read(db,actor,request,lambda current:context_row(db,current,matter,revision),matter=matter)
def target(db,actor,request,matter,username,revision):return guarded_read(db,actor,request,lambda current:target_row(db,current,matter,username,revision),matter=matter,username=username)


def client_allowed(db,actor,client_id,*,exclude_matter=None):
    client=db.get(m.Client,client_id)
    if not client or client_id in actor.client_walls:raise HTTPException(403,'Client administration denied')
    areas=admin.scopes(db,actor)-({exclude_matter} if exclude_matter else set())
    if client.created_by!=actor.id and db.scalar(select(m.MatterValidation.matter_id).where(m.MatterValidation.client_id==client_id,m.MatterValidation.matter_id.in_(areas)).limit(1)) is None:
        raise HTTPException(403,'Client administration denied')


def write(db,actor,request,operation,payload,*,matter=None):
    try:
        current=fresh(db,request,actor.id,matter)[2];target_before=None
        if operation=='access':target_before=target_row(db,current,matter,payload.username)
        if operation=='client':result=admin.create_client(db,current,payload.name,payload.client_number,commit=False)
        elif operation=='matter':
            client_allowed(db,current,payload.client_id)
            result=admin.create_matter(db,current,payload.client_id,payload.name,payload.matter_number,commit=False)
        elif operation=='decision':result=admin.decide(db,current,matter,payload,commit=False)
        else:result=admin.set_access(db,current,matter,payload,commit=False)
        current=fresh(db,request,actor.id,matter)[2]
        if operation=='matter':client_allowed(db,current,payload.client_id,exclude_matter=result['id'])
        if operation=='access':
            target_after=target_row(db,current,matter,payload.username)
            keys={'account_id','username','organization','blocked','effective_blocked','active'}
            if any(target_before[key]!=target_after[key] for key in keys):raise HTTPException(409,'Target context changed; reload before assigning')
        if matter is not None:
            validation=admin.require_matter(db,current,matter)
            if validation.revision!=payload.expected_revision+1:raise HTTPException(409,'Registry revision changed before command receipt')
        current=fresh(db,request,actor.id,matter)[2]
        if operation=='matter':client_allowed(db,current,payload.client_id,exclude_matter=result['id'])
        db.commit();return result
    except HTTPException:
        db.rollback();raise
