from urllib.parse import quote
from fastapi import APIRouter,Depends,HTTPException,Request,Response,Path
from kestrel.api.auth import identity,database
from kestrel.services import source_attachments as s

router=APIRouter(prefix='/api/v1/workflow/documents',tags=['Source-restricted staged email attachments'])

def checked(db,actor,call):
    try:return call()
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'source.attachment.denied','denied',actor.id,category='access');db.commit()
        raise

@router.get('/{source_id}/attachments')
def listing(source_id:str,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    return checked(db,actor[2],lambda:s.execute(db,actor[2],request,source_id,historical=historical))

@router.get('/{source_id}/attachments/{index}/download')
def download(source_id:str,index:int,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    if not 1<=index<=25:raise HTTPException(404,'Staged attachment unavailable')
    item=checked(db,actor[2],lambda:s.execute(db,actor[2],request,source_id,index,historical))
    return Response(item['data'],media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(item['file_name'],safe=''),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Content-SHA256':item['bytes_hash']})
