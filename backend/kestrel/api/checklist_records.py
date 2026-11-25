from fastapi import APIRouter,Depends
from kestrel.api.auth import identity,database
from kestrel.schemas.gate1_completion import RequestLog
from kestrel.services import checklist_records as s
router=APIRouter(prefix='/api/v1/checklist-records',tags=['Checklist history and request log'])
@router.get('/reports/{report_id}/coverage')
def report(report_id:str,actor=Depends(identity),db=Depends(database)):return s.report_coverage(db,actor[2],report_id)
@router.get('/{version_id}/items/{item_id}/history')
def history(version_id:str,item_id:str,actor=Depends(identity),db=Depends(database)):return s.history(db,actor[2],version_id,item_id)
@router.post('/{version_id}/items/{item_id}/requests',status_code=201)
def request(version_id:str,item_id:str,payload:RequestLog,actor=Depends(identity),db=Depends(database)):return s.request_log(db,actor[2],version_id,item_id,payload)
