from fastapi import APIRouter,Depends
from kestrel.api.auth import identity,database
from kestrel.schemas.vdr import MappingCreate,BatchCreate
from kestrel.services import vdr_imports as s
router=APIRouter(prefix='/api/v1/vdr-imports',tags=['VDR mappings and retained metadata staging'])

@router.get('/fields')
def fields(matter_id:str,actor=Depends(identity),db=Depends(database)):
    s.w.legal(actor[2],matter_id)
    return {'fields':s.FIELDS,'required':sorted(s.REQUIRED)}

@router.get('/profiles')
def profiles(matter_id:str,actor=Depends(identity),db=Depends(database)):
    return s.profiles(db,actor[2],matter_id)

@router.post('/profiles',status_code=201)
def create(payload:MappingCreate,actor=Depends(identity),db=Depends(database)):
    return s.create_profile(db,actor[2],payload)

@router.post('/batches',status_code=201)
def stage(payload:BatchCreate,actor=Depends(identity),db=Depends(database)):
    return s.stage(db,actor[2],payload)

@router.get('/batches/{batch_id}')
def batch(batch_id:str,actor=Depends(identity),db=Depends(database)):
    value=s.get_batch(db,actor[2],batch_id)
    row=db.get(s.VdrImportBatch,batch_id)
    s.audit(db,'vdr.batch.view','allowed',actor[2].id,category='legal_sme',matter_id=row.matter_id,object_id=batch_id)
    db.commit();return value
