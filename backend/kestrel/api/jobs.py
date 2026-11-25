import json
from typing import Literal
from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import AnalysisJob
from kestrel.services import jobs,governance

router=APIRouter(prefix='/api/v1/jobs',tags=['Synthetic analysis jobs'])

class Enqueue(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    playbook_id:str=Field(min_length=1,max_length=36)
    idempotency_key:str=Field(min_length=8,max_length=128,pattern=r'^[a-zA-Z0-9_-]+$')
    rationale:str=Field(min_length=5,max_length=1000)
    document_version_id:str | None=Field(default=None,max_length=36)
    engine_name:Literal['literal','openai']='literal'

class Retry(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(min_length=5,max_length=1000)

def output(row,detail=False):
    return {'id':row.id,'matter_id':row.matter_id,'playbook_id':row.playbook_id,'playbook_hash':row.playbook_hash,
        'requested_by':row.requested_by,'state':row.state,'attempts':row.attempts,'created_at':row.created_at,
        'coverage':(json.loads(row.result_json).get('coverage',[]) if row.result_json else []),'context_windows':(json.loads(row.result_json).get('context_windows') if row.result_json else None),'error_code':row.error_code,'lease_until':row.lease_until,'document_version_id':row.document_version_id,'engine_name':row.engine_name,
        **({'result':json.loads(row.result_json) if row.result_json else None} if detail else {})}

@router.post('',status_code=201)
def enqueue(payload:Enqueue,actor=Depends(identity),db=Depends(database)):
    return output(jobs.enqueue(db,actor[2],payload))

@router.get('')
def listing(matter_id:str,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    governance.access(actor[2],matter_id)
    rows=db.scalars(select(AnalysisJob).where(AnalysisJob.matter_id==matter_id).order_by(AnalysisJob.created_at.desc()).limit(100))
    result=[]
    from fastapi import HTTPException
    for row in rows:
        try:result.append(output(jobs.read(db,actor[2],row.id,historical)))
        except HTTPException as error:
            if error.status_code!=403:raise
    return result

@router.get('/{job_id}')
def get(job_id:str,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    return output(jobs.read(db,actor[2],job_id,historical),detail=True)

@router.post('/{job_id}/retry')
def retry(job_id:str,payload:Retry,actor=Depends(identity),db=Depends(database)):
    return output(jobs.retry(db,actor[2],jobs.read(db,actor[2],job_id),payload.rationale))
