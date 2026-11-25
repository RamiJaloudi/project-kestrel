from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import SourceAccessGrant as Grant,SourceVersion,Account,CleanTeamMembership
from kestrel.services import workflow as w,diligence
from kestrel.services.auth import clock
from kestrel.domain import Role as R,Organization as O,member_and_not_walled
from kestrel.repositories.identity import principal,clean_scope
router=APIRouter(prefix='/api/v1/source-access',tags=['Named Halden clean-team source access'])

class Propose(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    source_id:str=Field(min_length=1,max_length=36)
    username:str=Field(min_length=3,max_length=128)
    outside_business:Literal[True]
    expires_in_days:int=Field(ge=1,le=30)
    rationale:str=Field(min_length=10,max_length=1000)

class Reason(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(min_length=10,max_length=1000)

def target(db,account_id,matter):
    account=db.get(Account,account_id)
    if not account or not account.active:raise HTTPException(403,'Active named Halden person required')
    person=principal(db,account,clock())
    if person.org!=O.CLIENT or not member_and_not_walled(person,matter):raise HTTPException(403,'Assigned, unwalled Halden person required')
    return person

def checked(db,actor,source_id):
    row,policy=w.source(db,actor,source_id);w.legal(actor,row.matter_id)
    review=diligence.latest_review(db,row.id)
    if policy.classification!='clean_team' or not policy.clean_team_scope or policy.resource_type=='legal_advice' or policy.signing_frozen or policy.superseded or not review or review.coverage_state!='complete':raise HTTPException(409,'A current fully lawyer-reviewed clean-team source is required')
    return row,policy

def output(db,row):
    value={key:getattr(row,key) for key in ['id','source_id','account_id','proposed_by','approved_by','snapshot_hash','rationale','decision_rationale','state','expires_at','revocation_rationale','revoked_by','revoked_at']}
    account=db.get(Account,row.account_id)
    return {**value,'recipient_username':account.username if account else row.account_id}

@router.post('',status_code=201)
def propose(payload:Propose,actor=Depends(identity),db=Depends(database)):
    row,policy=checked(db,actor[2],payload.source_id)
    account=db.scalar(select(Account).where(Account.username==payload.username.casefold()))
    if not account:raise HTTPException(403,'Named eligible recipient required')
    target(db,account.id,row.matter_id)
    grant=Grant(source_id=row.id,account_id=account.id,proposed_by=actor[2].id,snapshot_hash=w.snapshot(db,policy),rationale='Outside-business designation explicitly attested. '+payload.rationale,expires_at=clock()+payload.expires_in_days*86400,created_at=clock())
    db.add(grant);db.flush();w.event(db,actor[2],policy,'source_grant.propose',grant.id);db.commit();return output(db,grant)

@router.get('')
def listing(matter_id:str,actor=Depends(identity),db=Depends(database)):
    w.legal(actor[2],matter_id);result=[]
    for grant in db.scalars(select(Grant).join(SourceVersion,SourceVersion.id==Grant.source_id).where(SourceVersion.matter_id==matter_id)):
        try:w.source(db,actor[2],grant.source_id);result.append(output(db,grant))
        except HTTPException as e:
            if e.status_code!=403:raise
    return result

@router.post('/{grant_id}/{decision}')
def decide(grant_id:str,decision:Literal['approve','reject','revoke'],payload:Reason,actor=Depends(identity),db=Depends(database)):
    grant=db.scalar(select(Grant).where(Grant.id==grant_id).with_for_update())
    if not grant:raise HTTPException(404,'Grant unavailable')
    source,policy=w.source(db,actor[2],grant.source_id);w.legal(actor[2],source.matter_id)
    if R.ANTITRUST not in actor[2].roles:raise HTTPException(403,'Cleared antitrust counsel required')
    if decision=='revoke':
        if grant.state!='approved':raise HTTPException(409,'Only active approvals can be revoked')
        grant.state='revoked';grant.revocation_rationale=payload.rationale;grant.revoked_by=actor[2].id;grant.revoked_at=clock()
    else:
        if grant.state!='pending' or grant.proposed_by==actor[2].id:raise HTTPException(403,'Independent pending-grant decision required')
        if decision=='approve':
            checked(db,actor[2],grant.source_id);target(db,grant.account_id,source.matter_id)
            if w.snapshot(db,policy)!=grant.snapshot_hash or grant.expires_at<=clock():raise HTTPException(409,'Grant snapshot changed or expired')
            if not clean_scope(db,grant.account_id,source.matter_id,policy.clean_team_scope,clock()):
                db.add(CleanTeamMembership(account_id=grant.account_id,matter_id=source.matter_id,scope=policy.clean_team_scope,approved_by=actor[2].id,starts_at=clock(),expires_at=grant.expires_at))
        grant.state='approved' if decision=='approve' else 'rejected';grant.approved_by=actor[2].id
    if decision!='revoke':grant.decision_rationale=payload.rationale
    w.event(db,actor[2],policy,'source_grant.'+decision,grant.id);db.commit();return output(db,grant)
