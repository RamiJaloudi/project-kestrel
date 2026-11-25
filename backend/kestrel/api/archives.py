from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import SourceArchive
from kestrel.services import archives as service,workflow as w
from kestrel.services.auth import audit
from kestrel.adapters import archive_store
router=APIRouter(prefix='/api/v1/archives',tags=['Protected local source archives'])
class Create(BaseModel):
    model_config=ConfigDict(extra='forbid')
    matter_id:str=Field(min_length=1,max_length=36)
    require_worm:bool=False
@router.post('',status_code=201)
def create(payload:Create,actor=Depends(identity),db=Depends(database)):return service.create(db,actor[2],payload.matter_id,payload.require_worm)
@router.get('')
def listing(matter_id:str,actor=Depends(identity),db=Depends(database)):
    w.legal(actor[2],matter_id);result=[]
    for row in db.scalars(select(SourceArchive).where(SourceArchive.matter_id==matter_id,SourceArchive.created_by==actor[2].id)):
        try:service.allowed(db,actor[2],row);result.append(service.output(row))
        except HTTPException as error:
            if error.status_code!=403:raise
    return result
@router.post('/{archive_id}/verify')
def verify(archive_id:str,actor=Depends(identity),db=Depends(database)):
    row=db.get(SourceArchive,archive_id)
    if not row:raise HTTPException(404,'Archive unavailable')
    manifest=service.allowed(db,actor[2],row)
    result=service.verify_content(archive_store.get(row.storage_key,row.protected_hash,row.content_hash),manifest)
    audit(db,'archive.verify','source_roundtrip_verified',actor[2].id,category='legal_sme',matter_id=row.matter_id,object_id=row.id);db.commit();return result
