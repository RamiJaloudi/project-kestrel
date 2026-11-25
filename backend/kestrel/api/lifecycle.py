import json
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import LifecycleDecision,MatterLifecycle
from kestrel.services import lifecycle as service,workflow as w
router=APIRouter(prefix='/api/v1/lifecycle',tags=['Signing, closing, legal holds and retention'])
class Propose(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(min_length=1,max_length=36)
    kind:Literal['sign','close','hold','release_hold','delete_client_copies']
    rationale:str=Field(min_length=10,max_length=1000)
class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    content_hash:str=Field(min_length=64,max_length=64)
    rationale:str=Field(min_length=10,max_length=1000)
@router.get('')
def status(matter_id:str,actor=Depends(identity),db=Depends(database)):
    service.control_access(actor[2],matter_id);state=db.get(MatterLifecycle,matter_id)
    try:w.legal(actor[2],matter_id);legal=True
    except HTTPException:legal=False
    return {'frozen':bool(state and state.frozen),'external_closed':bool(state and state.external_closed),'legal_hold':bool(state and state.legal_hold),'firm_retention':state.firm_retention if state else 'indefinite_pending_approved_retention_schedule','decisions':[service.output(r) for r in db.scalars(select(LifecycleDecision).where(LifecycleDecision.matter_id==matter_id).order_by(LifecycleDecision.created_at.desc())) if legal or r.kind in {'close','delete_client_copies'}]}
@router.post('',status_code=201)
def propose(payload:Propose,actor=Depends(identity),db=Depends(database)):return service.propose(db,actor[2],payload)
@router.get('/{decision_id}/manifest')
def manifest(decision_id:str,actor=Depends(identity),db=Depends(database)):
    row=db.get(LifecycleDecision,decision_id)
    if not row:raise HTTPException(404,'Decision unavailable')
    # Recheck clearance for the complete manifest before disclosing its inventory.
    if row.kind=='sign':service.manifest(db,actor[2],row.matter_id)
    else:service.control_access(actor[2],row.matter_id)
    return {'content_hash':row.content_hash,'manifest':json.loads(row.payload_json)}
@router.post('/{decision_id}/{decision}')
def decide(decision_id:str,decision:Literal['approve','reject'],payload:Decision,actor=Depends(identity),db=Depends(database)):
    row=db.scalar(select(LifecycleDecision).where(LifecycleDecision.id==decision_id).with_for_update())
    if not row:raise HTTPException(404,'Decision unavailable')
    return service.decide(db,actor[2],row,payload,decision)
