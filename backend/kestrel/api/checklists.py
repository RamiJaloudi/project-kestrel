from typing import Literal
from fastapi import APIRouter,Depends
from kestrel.api.auth import identity,database
from kestrel.schemas.ddr import ChecklistCreate,VersionDecision,CoverageDecision,ApplicabilityDecision
from kestrel.services import checklists as service
router=APIRouter(prefix='/api/v1/checklists',tags=['DDR request checklist foundation'])

@router.post('',status_code=201)
def create(payload:ChecklistCreate,actor=Depends(identity),db=Depends(database)):
    return service.create(db,actor[2],payload)
@router.get('')
def listing(matter_id:str,actor=Depends(identity),db=Depends(database)):
    return service.listing(db,actor[2],matter_id)
@router.get('/{version_id}')
def get(version_id:str,actor=Depends(identity),db=Depends(database)):
    return service.output(db,service.version(db,actor[2],version_id))
@router.get('/{version_id}/coverage')
def coverage(version_id:str,actor=Depends(identity),db=Depends(database)):
    return service.coverage(db,actor[2],version_id)
@router.post('/{version_id}/coverage/{item_id}',status_code=201)
def record(version_id:str,item_id:str,payload:CoverageDecision,actor=Depends(identity),db=Depends(database)):
    return service.set_coverage(db,actor[2],version_id,item_id,payload)
@router.post('/{version_id}/coverage/{item_id}/na-requests',status_code=201)
def request_na(version_id:str,item_id:str,payload:ApplicabilityDecision,actor=Depends(identity),db=Depends(database)):
    return service.request_na(db,actor[2],version_id,item_id,payload)
@router.post('/{version_id}/na-requests/{request_id}/{operation}')
def decide_na(version_id:str,request_id:str,operation:Literal['approve','reject'],payload:ApplicabilityDecision,actor=Depends(identity),db=Depends(database)):
    return service.decide_na(db,actor[2],version_id,request_id,operation,payload)
@router.post('/{version_id}/{operation}')
def transition(version_id:str,operation:Literal['submit','approve','reject','publish'],payload:VersionDecision,actor=Depends(identity),db=Depends(database)):
    return service.transition(db,actor[2],version_id,operation,payload)

@router.post('/{version_id}/coverage/{item_id}/waiver-requests',status_code=201)
def waiver(version_id:str,item_id:str,payload:ApplicabilityDecision,actor=Depends(identity),db=Depends(database)):
    return service.request_waiver(db,actor[2],version_id,item_id,payload)
@router.post('/{version_id}/waiver-requests/{request_id}/{operation}')
def decide_waiver(version_id:str,request_id:str,operation:Literal['approve','reject'],payload:ApplicabilityDecision,actor=Depends(identity),db=Depends(database)):
    return service.decide_waiver(db,actor[2],version_id,request_id,operation,payload)
