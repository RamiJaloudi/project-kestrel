import json
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from kestrel.api.auth import identity,database
from kestrel.models import CollaborationMessage as Message,CollaborationApproval as Approval,ReportVersion
from kestrel.services import workflow as w
from kestrel.services.auth import clock
from kestrel.domain import Role as R
from kestrel.adapters.extraction import digest
router=APIRouter(prefix='/api/v1/collaboration',tags=['Audience-scoped collaboration'])

class Write(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    release_id:str=Field(min_length=1,max_length=36)
    section_index:int | None=Field(default=None,ge=0,le=29,strict=True)
    parent_id:str | None=Field(default=None,max_length=36)
    kind:Literal['comment','question','reply']='question'
    body:str=Field(min_length=5,max_length=4000)

class Approve(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    kind:Literal['audience','antitrust']='audience'
    body_hash:str=Field(min_length=64,max_length=64)
    rationale:str=Field(min_length=5,max_length=1000)

def access(db,actor,release_id,write=False):
    release,policy=w.package(db,actor,release_id,internal=actor.org.value=='firm')
    if not policy.released:raise HTTPException(409,'Collaboration requires an audience-approved package')
    if write and any(p.signing_frozen or p.superseded for p in w.lineage(db,policy)):raise HTTPException(409,'Frozen or historical package is read-only')
    return release,policy

def section_context(db,release_id,index):
    if index is None:return
    report=db.scalar(select(ReportVersion).where(ReportVersion.release_id==release_id))
    if not report or index>=len(json.loads(report.body_json)['sections']):
        raise HTTPException(422,'Section unavailable in this exact report package')


def output(db,row,internal):
    approval=db.get(Approval,(row.id,'audience'))
    if digest(row.body.encode())!=row.body_hash:raise HTTPException(409,'Message integrity failure')
    approved=bool(approval and approval.body_hash==row.body_hash)
    if row.internal_draft and not internal and not approved:return None
    return {'id':row.id,'release_id':row.release_id,'section_index':row.section_index,'parent_id':row.parent_id,'author_id':row.author_id,'kind':row.kind,'body':row.body,'created_at':row.created_at,'body_hash':row.body_hash,'state':'lawyer_approved' if approved else 'firm_draft' if row.internal_draft else 'audience_message'}

@router.get('')
def listing(release_id:str,section_index:int | None=Query(default=None,ge=0,le=29),actor=Depends(identity),db=Depends(database)):
    _,policy=access(db,actor[2],release_id);section_context(db,release_id,section_index);result=[]
    statement=select(Message).where(Message.release_id==release_id)
    if section_index is not None:statement=statement.where(Message.section_index==section_index)
    for row in db.scalars(statement.order_by(Message.created_at,Message.id)):
        value=output(db,row,actor[2].org.value=='firm')
        if value:result.append(value)
    w.event(db,actor[2],policy,'collaboration.view',release_id);db.commit();return result

@router.post('',status_code=201)
def write(payload:Write,actor=Depends(identity),db=Depends(database)):
    _,policy=access(db,actor[2],payload.release_id,write=True)
    section_context(db,payload.release_id,payload.section_index)
    if payload.parent_id:
        parent=db.get(Message,payload.parent_id)
        if not parent or parent.release_id!=payload.release_id or output(db,parent,actor[2].org.value=='firm') is None:raise HTTPException(403,'Parent message unavailable')
        if payload.section_index is not None and payload.section_index!=parent.section_index:raise HTTPException(422,'Reply must retain its parent section context')
        payload.section_index=parent.section_index
    elif payload.kind=='reply':raise HTTPException(422,'Select a message to reply to')
    row=Message(**payload.model_dump(),author_id=actor[2].id,body_hash=digest(payload.body.encode()),internal_draft=actor[2].org.value=='firm',created_at=clock())
    db.add(row);db.flush();w.event(db,actor[2],policy,'collaboration.write',row.id,'draft' if row.internal_draft else 'received');db.commit()
    return output(db,row,True)

@router.post('/{message_id}/approve')
def approve(message_id:str,payload:Approve,actor=Depends(identity),db=Depends(database)):
    row=db.get(Message,message_id)
    if not row:raise HTTPException(404,'Message unavailable')
    _,policy=access(db,actor[2],row.release_id,write=True);w.legal(actor[2],policy.matter_id)
    if not row.internal_draft or actor[2].id==row.author_id:raise HTTPException(403,'Independent lawyer approval required for firm draft')
    if payload.body_hash!=row.body_hash:raise HTTPException(409,'Message changed')
    # The approver must be cleared for every underlying source, including clean-team scope.
    for item in w.lineage(db,policy)[1:]:w.require_policy(db,actor[2],item)
    if payload.kind=='antitrust' and R.ANTITRUST not in actor[2].roles:raise HTTPException(403,'Antitrust counsel required')
    if payload.kind=='audience' and any(p.classification=='clean_team' for p in w.lineage(db,policy)) and not db.get(Approval,(row.id,'antitrust')):raise HTTPException(409,'Separate antitrust approval of this exact reply is required')
    db.add(Approval(message_id=row.id,kind=payload.kind,actor_id=actor[2].id,body_hash=row.body_hash,rationale=payload.rationale,created_at=clock()))
    w.event(db,actor[2],policy,'collaboration.approve',row.id)
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Message already approved')
    return output(db,row,True)
