"""Administrative simulations over the same SQL-backed person and document policies."""
import json
from kestrel.services import policy as policy_engine
from datetime import datetime,timezone
from fastapi import HTTPException
from sqlalchemy import select,text,or_
from sqlalchemy.exc import IntegrityError
from kestrel import models as m
from kestrel.domain import Role as R,Organization as O
from kestrel.repositories.identity import principal
from kestrel.repositories.walls import state as wall_state,RELATIONSHIPS
from kestrel.services.auth import clock,audit
from kestrel.services import documents
from kestrel.adapters.extraction import canonical,digest

def operator(actor):
    if actor.org!=O.FIRM or not actor.roles&{R.ROOT_ADMIN,R.CONFLICTS}:raise HTTPException(403,'Scoped registry administrator or Conflicts approver required')

def scopes(db,actor):
    operator(actor);now=clock()
    return set(db.scalars(select(m.MatterAssignment.matter_id).where(m.MatterAssignment.account_id==actor.id,m.MatterAssignment.starts_at<=now,m.MatterAssignment.expires_at>now,m.MatterAssignment.revoked.is_(False))))-actor.walls

def scope(db,actor,client_number,matter_number=None):
    allowed=scopes(db,actor)
    client=db.scalar(select(m.Client).where(m.Client.client_number==client_number))
    if not client or client.id in actor.client_walls:raise HTTPException(403,'Client or matter unavailable for this operator')
    if matter_number is not None:
        validation=db.scalar(select(m.MatterValidation).where(m.MatterValidation.client_id==client.id,m.MatterValidation.matter_number==matter_number))
        if not validation or validation.matter_id not in allowed:raise HTTPException(403,'Client or matter unavailable for this operator')
        return client,validation
    children=set(db.scalars(select(m.MatterValidation.matter_id).where(m.MatterValidation.client_id==client.id)))
    if children:
        if not children<=allowed:raise HTTPException(403,'Client-wide operations require scope for every registered matter; choose a permitted client–matter pair')
    elif R.ROOT_ADMIN not in actor.roles or client.created_by!=actor.id:raise HTTPException(403,'Client or matter unavailable for this operator')
    return client,None

def account(db,username):
    rows=list(db.scalars(select(m.Account).where(or_(m.Account.username==username.strip().casefold(),m.Account.email==username.strip().casefold())).limit(2)))
    return rows[0] if len(rows)==1 else None

def context(db,actor):
    allowed=scopes(db,actor)
    clients=list(db.scalars(select(m.Client).outerjoin(m.MatterValidation,m.Client.id==m.MatterValidation.client_id).where(or_(m.MatterValidation.matter_id.in_(allowed),m.Client.created_by==actor.id)).order_by(m.Client.client_number)).unique())
    clients=[c for c in clients if c.id not in actor.client_walls]
    matters=[dict(row) for row in db.execute(text('SELECT * FROM vw_client_matter_validation')).mappings() if row['matter_id'] in allowed]
    people=list(db.scalars(select(m.Account).join(m.MatterAssignment,m.Account.id==m.MatterAssignment.account_id).where(m.MatterAssignment.matter_id.in_(allowed)).order_by(m.Account.username)).unique())
    return {'operator_id':actor.id,'operator_username':db.get(m.Account,actor.id).username,'clients':[{'client_number':c.client_number,'name':c.name} for c in clients],
        'matters':[{'client_number':r['client_number'],'matter_number':r['matter_number'],'name':r['matter_name'],'status':r['validation_status']} for r in matters],
        'people':[{'username':p.username,'active':p.active} for p in people],
        'roles':sorted(r.value for r in R),'relationships':RELATIONSHIPS,'actions':sorted(documents.ACTIONS),'operator_roles':sorted(r.value for r in actor.roles)}

def affects(db,actor,row):
    if row.account_id:return row.account_id==actor.id
    if row.role_name and R(row.role_name) not in actor.roles:return False
    if row.relationship_kind and row.entry_type!='relationship':
        relations=wall_state(db,actor.id,{r.value for r in actor.roles},clock())['relationships']
        if not any(r['client_id']==row.client_id and (r['matter_id'] is None or r['matter_id']==row.matter_id) and r['relationship_kind']==row.relationship_kind for r in relations):return False
    return True

def retired(db,row):
    return db.scalar(select(m.WallControl.id).join(m.WallControlDecision,m.WallControlDecision.control_id==m.WallControl.id).where(m.WallControl.retire_id==row.id,m.WallControlDecision.decision=='approve')) is not None

def control_output(db,row):
    client=db.get(m.Client,row.client_id);validation=db.get(m.MatterValidation,row.matter_id) if row.matter_id else None
    target=db.get(m.Account,row.account_id) if row.account_id else None;decision=db.get(m.WallControlDecision,row.id)
    gone=retired(db,row)
    return {'id':row.id,'entry_type':row.entry_type,'client_number':client.client_number,'matter_number':validation.matter_number if validation else None,
        'username':target.username if target else None,'proposed_by_username':db.get(m.Account,row.proposed_by).username,'role_name':row.role_name,'relationship_kind':row.relationship_kind,'proposed_by':row.proposed_by,
        'state':decision.decision if decision else 'pending','reviewer_id':decision.actor_id if decision else None,
        'rationale':row.rationale,'decision_rationale':decision.rationale if decision else None,'starts_at':row.starts_at,'expires_at':row.expires_at,
        'retire_id':row.retire_id,'retired':gone,'active':bool(decision and decision.decision=='approve' and row.entry_type!='retirement' and not gone and row.starts_at<=clock() and (row.expires_at is None or clock()<row.expires_at))}

def propose(db,actor,payload):
    client,validation=scope(db,actor,payload.client_number,payload.matter_number)
    target=account(db,payload.username) if payload.username else None
    if payload.username and not target:raise HTTPException(422,'Select an existing unambiguous person')
    if payload.role_name and payload.role_name not in {r.value for r in R}:raise HTTPException(422,'Known server role required')
    if payload.relationship_kind and payload.relationship_kind not in RELATIONSHIPS:raise HTTPException(422,'Known relationship required')
    if payload.entry_type=='relationship' and (not target or not payload.relationship_kind or payload.role_name):raise HTTPException(422,'Relationships require a named person and relationship kind; no role selector')
    if payload.entry_type=='restriction' and not any([target,payload.role_name,payload.relationship_kind]):raise HTTPException(422,'At least one restriction selector required')
    now=clock();row=m.WallControl(client_id=client.id,matter_id=validation.matter_id if validation else None,entry_type=payload.entry_type,account_id=target.id if target else None,role_name=payload.role_name,relationship_kind=payload.relationship_kind,starts_at=now,expires_at=now+payload.days*86400 if payload.days else None,proposed_by=actor.id,rationale=payload.rationale,created_at=now)
    if affects(db,actor,row):raise HTTPException(403,'Self-access control changes are prohibited')
    db.add(row);db.flush();audit(db,'walls.propose','pending',actor.id,matter_id=row.matter_id,object_id=row.id);db.commit();return control_output(db,row)

def propose_retirement(db,actor,row,rationale):
    client=db.get(m.Client,row.client_id);validation=db.get(m.MatterValidation,row.matter_id) if row.matter_id else None
    scope(db,actor,client.client_number,validation.matter_number if validation else None)
    decision=db.get(m.WallControlDecision,row.id)
    if row.entry_type=='retirement' or not decision or decision.decision!='approve' or retired(db,row):raise HTTPException(409,'An approved non-retired control is required')
    if affects(db,actor,row):raise HTTPException(403,'Self-access control changes are prohibited')
    now=clock();proposal=m.WallControl(client_id=row.client_id,matter_id=row.matter_id,entry_type='retirement',account_id=row.account_id,role_name=row.role_name,relationship_kind=row.relationship_kind,starts_at=now,expires_at=None,proposed_by=actor.id,retire_id=row.id,rationale=rationale,created_at=now)
    db.add(proposal);db.flush();audit(db,'walls.retirement_proposed','pending',actor.id,matter_id=row.matter_id,object_id=proposal.id);db.commit();return control_output(db,proposal)

def decide(db,actor,row,decision,rationale):
    # Serialize approvals/retirements per client; never mutate the old evidence row.
    db.scalar(select(m.Client).where(m.Client.id==row.client_id).with_for_update())
    db.expire_all();reviewer=db.get(m.Account,actor.id)
    if not reviewer or not reviewer.active:raise HTTPException(403,'Active Conflicts reviewer required')
    actor=principal(db,reviewer,clock());row=db.get(m.WallControl,row.id)
    client=db.get(m.Client,row.client_id);validation=db.get(m.MatterValidation,row.matter_id) if row.matter_id else None
    scope(db,actor,client.client_number,validation.matter_number if validation else None)
    if R.CONFLICTS not in actor.roles or row.proposed_by==actor.id or affects(db,actor,row):raise HTTPException(403,'Independent unaffected Conflicts approver required')
    if db.get(m.WallControlDecision,row.id):raise HTTPException(409,'Control already decided')
    if decision=='approve' and row.entry_type!='retirement' and row.expires_at is not None and row.expires_at<=clock():raise HTTPException(409,'Control expired before approval; propose a fresh control')
    if decision=='approve' and row.retire_id and retired(db,db.get(m.WallControl,row.retire_id)):raise HTTPException(409,'Original control already retired')
    db.add(m.WallControlDecision(control_id=row.id,actor_id=actor.id,decision=decision,rationale=rationale,created_at=clock()))
    audit(db,'walls.'+decision,decision,actor.id,matter_id=row.matter_id,object_id=row.id)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent decision; refresh')
    return control_output(db,row)

def controls(db,actor,client_number,matter_number=None):
    client,validation=scope(db,actor,client_number,matter_number)
    statement=select(m.WallControl).where(m.WallControl.client_id==client.id)
    if validation:statement=statement.where(or_(m.WallControl.matter_id.is_(None),m.WallControl.matter_id==validation.matter_id))
    return [control_output(db,row) for row in db.scalars(statement.order_by(m.WallControl.created_at.desc(),m.WallControl.id).limit(200))]

def resolve_document(db,reference_id):
    policy_id=db.scalar(select(m.SourceVersion.policy_id).where(m.SourceVersion.id==reference_id))
    return documents.load(db,policy_id or reference_id)

def catalogue(db,actor,client_number,matter_number):
    _,validation=scope(db,actor,client_number,matter_number);result=[]
    if not validation:raise HTTPException(422,'Choose a client–matter pair')
    rows=list(db.execute(text('SELECT * FROM vw_wall_document_references WHERE matter_id=:matter ORDER BY policy_id LIMIT 201'),{'matter':validation.matter_id}).mappings())
    for ref in rows[:200]:
        policy=documents.load(db,ref['policy_id']);can_read=policy_engine.evaluate(db,actor,policy,'historical_read' if policy.superseded else 'read',clock())['allowed']
        label='Restricted policy reference · '+policy.id[:8]
        if can_read:
            source=db.execute(select(m.SourceVersion.logical_key,m.SourceVersion.version_number,m.SourceVersion.file_name).where(m.SourceVersion.id==ref['source_version_id'])).first() if ref['source_version_id'] else None
            label=f'{source.logical_key} v{source.version_number} · {source.file_name}' if source else policy.resource_type.capitalize()+' · '+policy.id[:8]
        result.append({'reference_id':policy.id,'label':label,'can_read':can_read})
    return {'documents':result,'truncated':len(rows)>200,'notice':'Policy references permit a decision check, not content access. Restricted names and attributes stay hidden.'}

def check(db,actor,payload):
    client,validation=scope(db,actor,payload.client_number,payload.matter_number)
    if payload.document_version_ids and not validation:raise HTTPException(422,'Document checks require an explicit client–matter pair')
    now=clock();target=account(db,payload.username);subject=principal(db,target,now) if target else None
    active=bool(target and target.active)
    state=wall_state(db,target.id,{r.value for r in subject.roles},now) if subject else {'client':{},'matter':{},'relationships':[]}
    client_blocked=client.id in state['client'];matter_blocked=bool(subject and validation and validation.matter_id in subject.walls and not client_blocked)
    assigned=bool(subject and validation and db.scalar(select(m.MatterAssignment.id).where(
        m.MatterAssignment.account_id==subject.id,m.MatterAssignment.matter_id==validation.matter_id,
        m.MatterAssignment.starts_at<=now,m.MatterAssignment.expires_at>now,m.MatterAssignment.revoked.is_(False)).limit(1)))
    role_eligible=bool(subject and ((subject.org==O.FIRM and subject.roles&{R.LAWYER,R.SME,R.ANTITRUST}) or (subject.org==O.CLIENT and R.CLIENT in subject.roles) or (subject.org==O.BANK and R.BANK in subject.roles)))
    reasons=[]
    if not active:reasons.append('PERSON_UNAVAILABLE_OR_INACTIVE')
    if client_blocked:reasons.append('CLIENT_RESTRICTED')
    if matter_blocked:reasons.append('MATTER_RESTRICTED')
    if validation:
        if validation.status!='validated':reasons.append('MATTER_NOT_VALIDATED')
        if not assigned:reasons.append('NO_ACTIVE_MATTER_ASSIGNMENT')
        if not role_eligible:reasons.append('ROLE_NOT_CONTENT_ELIGIBLE')
        lifecycle=db.get(m.MatterLifecycle,validation.matter_id)
        if lifecycle and lifecycle.external_closed and subject and subject.org!=O.FIRM:reasons.append('EXTERNAL_WORKSPACE_CLOSED')
        if lifecycle and lifecycle.frozen and payload.action in {'analyze','edit','share','export'}:reasons.append('SIGNING_FROZEN')
    eligible=not reasons if validation else None
    relations=[{'kind':r['relationship_kind'],'scope':'matter' if r['matter_id'] else 'client','expires_at':r['expires_at']} for r in state['relationships'] if r['client_id']==client.id and (r['matter_id'] is None or validation and r['matter_id']==validation.matter_id)]
    person={'username':target.username if subject else 'Unavailable person','roles':sorted(r.value for r in subject.roles) if subject else [],'organization':subject.org.value if subject else None,'active':active,'client_restricted':client_blocked,'matter_restricted':matter_blocked,'assignment_active':assigned if validation else None,'role_eligible':role_eligible,'eligible':eligible,'relationships':relations,'reason_codes':reasons or ['NO_RECORDED_RESTRICTION']}
    decisions=[];document_snapshots={}
    for reference in payload.document_version_ids:
        allowed=False;reason=reasons[0] if reasons else 'DOCUMENT_UNAVAILABLE_OR_DENIED'
        if eligible:
            policy=resolve_document(db,reference)
            if policy and policy.matter_id==validation.matter_id:
                value=policy_engine.evaluate(db,subject,policy,payload.action,now);allowed=value['allowed']
                try:document_snapshots[reference]=documents.snapshot(db,policy)
                except ValueError:document_snapshots[reference]='invalid-lineage'
                # Operators only get detailed denial codes if their own document rights allow it.
                own=policy_engine.evaluate(db,actor,policy,'historical_read' if policy.superseded else 'read',now)['allowed']
                reason=value['reason_code'] if own or allowed else 'DOCUMENT_POLICY_DENIED'
        decisions.append({'reference_id':reference,'allowed':allowed,'reason_code':reason})
    fingerprint=digest(canonical({'person':person,'client_controls':state['client'].get(client.id,[]),'matter_controls':state['matter'].get(validation.matter_id,[]) if validation else [],'document_snapshots':document_snapshots,'decisions':decisions,'action':payload.action}).encode())
    value={'operator':{'id':actor.id,'username':db.get(m.Account,actor.id).username,'roles':sorted(r.value for r in actor.roles)},'decision_fingerprint':fingerprint,'checked_at':datetime.fromtimestamp(now,timezone.utc).isoformat(),'client_number':client.client_number,'matter_number':validation.matter_number if validation else None,'action':payload.action,'simulation_only':True,'person':person,'documents':decisions,
        'allowed':eligible and all(d['allowed'] for d in decisions) if validation else False if reasons else None,
        'policy_version':'person-document-abac-1','notice':'Point-in-time policy precheck only. No recorded wall is not a legal conflicts clearance or an access grant. Processing restrictions, workflow approvals and execution-time authorization still apply.'}
    retained=json.loads(canonical(value))
    for doc in retained['documents']:
        if not doc['allowed'] and doc['reason_code'] not in person['reason_codes']:doc['reason_code']='DOCUMENT_POLICY_DENIED'
    row=m.WallCheckRecord(actor_id=actor.id,subject_id=target.id if target else None,client_id=client.id,matter_id=validation.matter_id if validation else None,result_json=canonical(retained),created_at=now)
    db.add(row);db.flush();audit(db,'walls.check','denied' if value['allowed'] is False else 'checked',actor.id,matter_id=row.matter_id,object_id=row.id);db.commit()
    return {'receipt_id':row.id,**value}

def history(db,actor,client_number,matter_number=None):
    client,validation=scope(db,actor,client_number,matter_number)
    query=select(m.WallCheckRecord).where(m.WallCheckRecord.client_id==client.id)
    if validation:query=query.where(m.WallCheckRecord.matter_id==validation.matter_id)
    rows=[]
    for row in db.scalars(query.order_by(m.WallCheckRecord.created_at.desc(),m.WallCheckRecord.id).limit(20)):
        value=json.loads(row.result_json)
        rows.append({'receipt_id':row.id,'checked_at':value['checked_at'],'checked_by':value.get('operator',{}).get('username',db.get(m.Account,row.actor_id).username),'person':value['person']['username'],'action':value['action'],'allowed':value['allowed'],'document_count':len(value['documents'])})
    return rows

def receipt(db,actor,row):
    client=db.get(m.Client,row.client_id);validation=db.get(m.MatterValidation,row.matter_id) if row.matter_id else None
    scope(db,actor,client.client_number,validation.matter_number if validation else None)
    value=json.loads(row.result_json);value['notice']='Historical decision, not current authorization. Run a fresh check before acting. '+value['notice']
    audit(db,'walls.receipt_view','allowed',actor.id,matter_id=row.matter_id,object_id=row.id);db.commit()
    return {'receipt_id':row.id,**value}
