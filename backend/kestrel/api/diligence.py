from datetime import date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.services import diligence as service,workflow
from kestrel.models import Account
from kestrel.repositories.identity import principal
from kestrel.services.auth import clock

router=APIRouter(prefix='/api/v1/diligence',tags=['Board priorities, registers and lawyer assessments'])

class Evidence(BaseModel):
    model_config=ConfigDict(extra='forbid')
    unit:int=Field(ge=1)
    quote:str=Field(min_length=1,max_length=6000)
    start:int | None=Field(default=None,ge=0)

class Assessment(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    source_id:str=Field(max_length=36)
    expected_revision:int=Field(ge=0)
    decision:Literal['reviewed','rejected']
    summary:str=Field(min_length=10,max_length=2000)
    topic:Literal['change_of_control','assignment','exclusivity','non_compete','termination','liability_cap','governing_law','data_protection','other']
    severity:Literal['critical','high','medium','low','information']
    materiality:Literal['material','not_material','undetermined']
    exposure:Literal['consent','notice','termination','none','unclear']
    workflow_status:Literal['open','in_progress','resolved']
    action:str=Field(min_length=5,max_length=2000)
    owner_id:str | None=Field(default=None,max_length=36)
    due_on:date | None=None
    rationale:str=Field(min_length=5,max_length=1000)
    evidence:list[Evidence]=Field(min_length=1,max_length=10)

class DocumentReview(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    expected_revision:int=Field(ge=0)
    title:str=Field(min_length=3,max_length=160)
    counterparty:str=Field(default='',max_length=160)
    scope:Literal['customer','supplier','licence','corporate','employment','ip','real_estate','litigation','financial','other']
    coverage_state:Literal['not_started','in_review','complete']
    rationale:str=Field(min_length=5,max_length=1000)

@router.get('/board')
def board(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.finding_tables import guarded_read
    from kestrel.api.data_tables import checked
    return checked(db,actor[2],'findings.board',lambda:guarded_read(db,actor[2],matter_id,request,lambda fresh,audited:service.board(db,fresh,matter_id,audited=audited)))

@router.get('/owners')
def owners(source_id:str,request:Request,finding_id:str|None=None,actor=Depends(identity),db=Depends(database)):
    from kestrel.services import finding_tables
    from kestrel.api.data_tables import checked
    row,_=workflow.source(db,actor[2],source_id)
    return checked(db,actor[2],'findings.owners',lambda:finding_tables.guarded_read(db,actor[2],row.matter_id,request,lambda fresh,audited:finding_tables.owners(db,fresh,source_id,finding_id)))

@router.post('/findings',status_code=201)
def manual(payload:Assessment,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.finding_tables import save
    from kestrel.api.data_tables import checked
    return checked(db,actor[2],'findings.save',lambda:save(db,actor[2],payload,request))

@router.post('/findings/{finding_id}/revisions',status_code=201)
def correct(finding_id:str,payload:Assessment,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.finding_tables import save
    from kestrel.api.data_tables import checked
    return checked(db,actor[2],'findings.save',lambda:save(db,actor[2],payload,request,finding_id))

@router.get('/findings/{finding_id}/history')
def history(finding_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services import finding_tables
    from kestrel.api.data_tables import checked
    row,policy=service.resolve(db,actor[2],finding_id,historical=True)
    return checked(db,actor[2],'findings.history',lambda:finding_tables.guarded_read(db,actor[2],policy.matter_id,request,lambda fresh,audited:service.history(db,fresh,finding_id,audited=audited)))

@router.post('/documents/{source_id}/reviews',status_code=201)
def review_document(source_id:str,payload:DocumentReview,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.finding_tables import save_source_review
    from kestrel.api.data_tables import checked
    return checked(db,actor[2],'findings.source_review',lambda:save_source_review(db,actor[2],source_id,payload,request))
