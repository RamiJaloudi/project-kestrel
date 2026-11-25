from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from kestrel.api.auth import identity,database
from kestrel.api.integrations import caller
from kestrel.models import WallControl,WallCheckRecord
from kestrel.services import wall_checker as service
router=APIRouter(prefix='/api/v1/wall-checker',tags=['Person and document ethical-wall checks'])
class Scope(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    client_number:str=Field(pattern=r'^[0-9]{1,12}$',strict=True)
    matter_number:str | None=Field(default=None,pattern=r'^[0-9]{1,12}$',strict=True)
class Check(Scope):
    username:str=Field(min_length=1,max_length=254)
    action:Literal['read','download','analyze','edit','export','export_metadata','share','historical_read','triage']='read'
    document_version_ids:list[str]=Field(default_factory=list,max_length=50)
class Propose(Scope):
    entry_type:Literal['restriction','relationship']
    username:str | None=Field(default=None,min_length=1,max_length=254)
    role_name:str | None=Field(default=None,max_length=64)
    relationship_kind:str | None=Field(default=None,max_length=64)
    days:int | None=Field(default=None,ge=1,le=365)
    rationale:str=Field(min_length=10,max_length=1000)
class Reason(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(min_length=10,max_length=1000)

class RelationshipEvidence(BaseModel):
    kind:str
    scope:Literal['client','matter']
    expires_at:int | None
class PersonResult(BaseModel):
    username:str
    roles:list[str]
    organization:str | None
    active:bool
    client_restricted:bool
    matter_restricted:bool
    assignment_active:bool | None
    role_eligible:bool
    eligible:bool | None
    relationships:list[RelationshipEvidence]
    reason_codes:list[str]
class DocumentResult(BaseModel):
    reference_id:str
    allowed:bool
    reason_code:str
class OperatorEvidence(BaseModel):
    id:str
    username:str
    roles:list[str]
class CheckResult(BaseModel):
    operator:OperatorEvidence
    decision_fingerprint:str
    receipt_id:str
    checked_at:str
    client_number:str
    matter_number:str | None
    action:str
    simulation_only:Literal[True]
    person:PersonResult
    documents:list[DocumentResult]
    allowed:bool | None
    policy_version:str
    notice:str
class PolicyReference(BaseModel):
    reference_id:str
    label:str
    can_read:bool
class Catalogue(BaseModel):
    documents:list[PolicyReference]
    truncated:bool
    notice:str
class ControlResult(BaseModel):
    id:str
    entry_type:Literal['relationship','restriction','retirement']
    client_number:str
    matter_number:str | None
    username:str | None
    proposed_by_username:str
    role_name:str | None
    relationship_kind:str | None
    proposed_by:str
    state:Literal['pending','approve','reject']
    reviewer_id:str | None
    rationale:str
    decision_rationale:str | None
    starts_at:int
    expires_at:int | None
    retire_id:str | None
    retired:bool
    active:bool
class ClientChoice(BaseModel):
    client_number:str
    name:str
class MatterChoice(ClientChoice):
    matter_number:str
    status:str
class PersonChoice(BaseModel):
    username:str
    active:bool
class Context(BaseModel):
    operator_id:str
    operator_username:str
    operator_roles:list[str]
    clients:list[ClientChoice]
    matters:list[MatterChoice]
    people:list[PersonChoice]
    roles:list[str]
    relationships:dict[str,str]
    actions:list[str]
class CheckSummary(BaseModel):
    receipt_id:str
    checked_at:str
    checked_by:str
    person:str
    action:str
    allowed:bool | None
    document_count:int

@router.get('/context',response_model=Context)
def context(actor=Depends(caller('EthicalWalls.Check')),db=Depends(database)):return service.context(db,actor)
@router.get('/documents',response_model=Catalogue)
def documents(client_number:str,matter_number:str,actor=Depends(caller('EthicalWalls.Check')),db=Depends(database)):return service.catalogue(db,actor,client_number,matter_number)
@router.post('/check',response_model=CheckResult)
def check(payload:Check,actor=Depends(caller('EthicalWalls.Check')),db=Depends(database)):
    if len(set(payload.document_version_ids))!=len(payload.document_version_ids) or any(not 1<=len(v)<=36 for v in payload.document_version_ids):raise HTTPException(422,'Use 1–50 distinct bounded source or policy version IDs')
    return service.check(db,actor,payload)
@router.get('/checks',response_model=list[CheckSummary])
def history(client_number:str,matter_number:str|None=None,actor=Depends(caller('EthicalWalls.Check')),db=Depends(database)):
    return service.history(db,actor,client_number,matter_number)
@router.get('/checks/{receipt_id}',response_model=CheckResult)
def receipt(receipt_id:str,actor=Depends(caller('EthicalWalls.Check')),db=Depends(database)):
    service.operator(actor)
    row=db.get(WallCheckRecord,receipt_id)
    if not row:raise HTTPException(404,'Decision receipt unavailable')
    return service.receipt(db,actor,row)
@router.get('/controls',response_model=list[ControlResult])
def controls(client_number:str,matter_number:str|None=None,actor=Depends(identity),db=Depends(database)):return service.controls(db,actor[2],client_number,matter_number)
@router.post('/controls',status_code=201,response_model=ControlResult)
def propose(payload:Propose,actor=Depends(identity),db=Depends(database)):return service.propose(db,actor[2],payload)
@router.post('/controls/{control_id}/retire',status_code=201,response_model=ControlResult)
def retire(control_id:str,payload:Reason,actor=Depends(identity),db=Depends(database)):
    service.operator(actor[2])
    row=db.get(WallControl,control_id)
    if not row:raise HTTPException(404,'Control unavailable')
    return service.propose_retirement(db,actor[2],row,payload.rationale)
@router.post('/controls/{control_id}/{decision}',response_model=ControlResult)
def decide(control_id:str,decision:Literal['approve','reject'],payload:Reason,actor=Depends(identity),db=Depends(database)):
    service.operator(actor[2])
    row=db.get(WallControl,control_id)
    if not row:raise HTTPException(404,'Control unavailable')
    return service.decide(db,actor[2],row,decision,payload.rationale)
