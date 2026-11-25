from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from kestrel.api.auth import identity,database
from kestrel.models import ProcessingReplacement,Matter,GovernanceVersion
from kestrel.domain import Role as R,Organization as O,member_and_not_walled
from kestrel.services import governance
from kestrel.services.auth import audit,clock
router=APIRouter(prefix='/api/v1/processing-policy',tags=['Independent processing policy replacement'])
def scope(actor,matter):
    if actor.org!=O.FIRM or not actor.roles&{R.ROOT_ADMIN,R.SECURITY} or not member_and_not_walled(actor,matter):raise HTTPException(403,'Scoped processing policy approver required')
def pair(db,actor,old_id,new_id):
    old=db.get(GovernanceVersion,old_id);new=db.get(GovernanceVersion,new_id)
    if not old or not new:raise HTTPException(404,'Processing policies unavailable')
    scope(actor,old.matter_id)
    db.scalar(select(Matter).where(Matter.id==old.matter_id).with_for_update())
    if old.id==new.id or old.matter_id!=new.matter_id or any(p.kind!='environment_policy' or p.state!='published' or p.approved_hash!=p.content_hash or governance.definition(__import__('json').loads(p.definition_json))[1]!=p.content_hash for p in [old,new]):raise HTTPException(409,'Same-matter independently approved published processing versions required')
    retired=set(db.scalars(select(ProcessingReplacement.old_id).where(ProcessingReplacement.state=='approved')))
    if old.id in retired or new.id in retired:raise HTTPException(409,'Policy is already replaced; refresh active versions')
    return old,new
class Proposal(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    old_id:str=Field(max_length=36)
    new_id:str=Field(max_length=36)
    rationale:str=Field(min_length=5,max_length=1000)
class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(min_length=5,max_length=1000)
def output(row):return {k:getattr(row,k) for k in ['id','old_id','new_id','proposed_by','approved_by','state','rationale','decision_rationale']}
@router.get('/matters')
def matters(actor=Depends(identity),db=Depends(database)):
    if not actor[2].roles&{R.ROOT_ADMIN,R.SECURITY}:raise HTTPException(403,'Processing governance role required')
    return [{'id':r.id,'name':r.name} for r in db.scalars(select(Matter).where(Matter.id.in_(actor[2].matters-actor[2].walls)))]
@router.get('')
def listing(matter_id:str,actor=Depends(identity),db=Depends(database)):
    scope(actor[2],matter_id)
    return [output(r) for r in db.scalars(select(ProcessingReplacement).join(GovernanceVersion,ProcessingReplacement.old_id==GovernanceVersion.id).where(GovernanceVersion.matter_id==matter_id))]
@router.post('',status_code=201)
def propose(payload:Proposal,actor=Depends(identity),db=Depends(database)):
    old,new=pair(db,actor[2],payload.old_id,payload.new_id)
    row=ProcessingReplacement(old_id=old.id,new_id=new.id,proposed_by=actor[2].id,rationale=payload.rationale,created_at=clock());db.add(row)
    try:db.flush();audit(db,'processing.replace.request','pending',actor[2].id,matter_id=old.matter_id,object_id=row.id);db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Replacement already requested')
    return output(row)
@router.post('/{request_id}/{operation}')
def decide(request_id:str,operation:str,payload:Decision,actor=Depends(identity),db=Depends(database)):
    row=db.scalar(select(ProcessingReplacement).where(ProcessingReplacement.id==request_id).with_for_update())
    if not row:raise HTTPException(404,'Request unavailable')
    old,new=pair(db,actor[2],row.old_id,row.new_id)
    if row.state!='pending':raise HTTPException(409,'Replacement already decided')
    if operation not in {'approve','reject'}:raise HTTPException(422,'Choose approve or reject')
    if R.SECURITY not in actor[2].roles or actor[2].id in {row.proposed_by,new.author_id}:raise HTTPException(403,'Independent Security approver required')
    row.state='approved' if operation=='approve' else 'rejected';row.approved_by=actor[2].id;row.decision_rationale=payload.rationale
    audit(db,'processing.replace.'+operation,row.state,actor[2].id,matter_id=old.matter_id,object_id=row.id);db.commit();return output(row)
