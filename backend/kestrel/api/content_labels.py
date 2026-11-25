from typing import Literal
from fastapi import APIRouter,Depends
from kestrel.api.auth import identity,database
from kestrel.schemas.content_labels import Proposal,Decision
from kestrel.services import content_labels as s
router=APIRouter(prefix='/api/v1/content-labels',tags=['Document and segment content labels'])
@router.get('/impacts')
def impacts(matter_id:str,actor=Depends(identity),db=Depends(database)):return s.impacts(db,actor[2],matter_id)
@router.get('/sources/{source_id}')
def get(source_id:str,actor=Depends(identity),db=Depends(database)):return s.listing(db,actor[2],source_id)
@router.post('/sources/{source_id}',status_code=201)
def propose(source_id:str,payload:Proposal,actor=Depends(identity),db=Depends(database)):return s.propose(db,actor[2],source_id,payload)
@router.post('/assertions/{assertion_id}/{operation}')
def decide(assertion_id:str,operation:Literal['confirm','contest'],payload:Decision,actor=Depends(identity),db=Depends(database)):return s.decide(db,actor[2],assertion_id,operation,payload)

from pydantic import BaseModel,ConfigDict,Field
class ImpactAssignment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    assignee_id:str=Field(min_length=1,max_length=36)
@router.post('/impacts/{impact_id}/assign',status_code=201)
def assign(impact_id:str,payload:ImpactAssignment,actor=Depends(identity),db=Depends(database)):return s.assign_impact(db,actor[2],impact_id,payload.assignee_id)

@router.get('/impacts/{impact_id}/eligible-counsel')
def eligible(impact_id:str,actor=Depends(identity),db=Depends(database)):return s.eligible_counsel(db,actor[2],impact_id)
