from fastapi import APIRouter,Depends
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import OCRJob,SourceVersion
from kestrel.services import ocr_jobs as service,workflow as w
router=APIRouter(prefix='/api/v1/ocr',tags=['Offline scanned document recognition'])
class Verify(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    text_hash:str=Field(min_length=64,max_length=64)
    rationale:str=Field(min_length=5,max_length=1000)
def output(row):return {'id':row.id,'source_id':row.source_id,'state':row.state,'result_source_id':row.result_source_id,'error_code':row.error_code}
@router.post('/{source_id}',status_code=201)
def queue(source_id:str,actor=Depends(identity),db=Depends(database)):return output(service.enqueue(db,actor[2],source_id))
@router.post('/{source_id}/verify')
def verify(source_id:str,payload:Verify,actor=Depends(identity),db=Depends(database)):
    service.verify(db,actor[2],source_id,payload);return {'verified':True}
@router.get('')
def listing(matter_id:str,actor=Depends(identity),db=Depends(database)):
    from fastapi import HTTPException
    w.legal(actor[2],matter_id);rows=[]
    for row in db.scalars(select(OCRJob).join(SourceVersion,OCRJob.source_id==SourceVersion.id).where(SourceVersion.matter_id==matter_id)):
        try:w.source(db,actor[2],row.result_source_id or row.source_id,historical=True);rows.append(output(row))
        except HTTPException as error:
            if error.status_code!=403:raise
    return rows
