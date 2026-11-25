from typing import Literal
from fastapi import APIRouter,Depends,Response,Request,HTTPException,Query
from kestrel.api.auth import identity,database
from kestrel.schemas.data_tables import TableQuery,Export,TaskSelection,TaskReassign
from kestrel.services import data_tables as s
router=APIRouter(prefix='/api/v1/tables',tags=['Authorized DataTables and selected metadata exports'])
def checked(db,actor,operation,call):
    try:return call()
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'table.'+operation+'.denied','denied',actor.id,category='access');db.commit()
        raise
@router.post('/{view}/query')
def query(view:Literal['inventory','financial','tasks','findings'],payload:TableQuery,request:Request,actor=Depends(identity),db=Depends(database)):return checked(db,actor[2],'query',lambda:s.query(db,actor[2],view,payload,request))
@router.post('/{view}/export')
def export(view:Literal['inventory','financial','tasks','findings'],payload:Export,request:Request,actor=Depends(identity),db=Depends(database)):
    data,media,headers=checked(db,actor[2],'export',lambda:s.export(db,actor[2],view,payload,request));return Response(data,media_type=media,headers=headers)

@router.post('/tasks/eligible-people')
def task_people(payload:TaskSelection,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services import task_tables
    return checked(db,actor[2],'tasks.people',lambda:task_tables.people(db,actor[2],payload,request))

@router.post('/tasks/bulk-reassign')
def task_reassign(payload:TaskReassign,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services import task_tables
    return checked(db,actor[2],'tasks.bulk_reassign',lambda:task_tables.reassign(db,actor[2],payload,request))

@router.get('/findings/source-profile/{source_id}')
def finding_source(source_id:str,request:Request,matter_id:str=Query(min_length=1,max_length=36),historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.services import finding_tables
    return checked(db,actor[2],'findings.source_profile',lambda:finding_tables.profile_read(db,actor[2],source_id,matter_id,historical,request))

@router.get('/findings/{finding_id}')
def finding_detail(finding_id:str,request:Request,matter_id:str=Query(min_length=1,max_length=36),revision_id:str=Query(min_length=1,max_length=36),historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.services import finding_tables
    return checked(db,actor[2],'findings.detail',lambda:finding_tables.detail(db,actor[2],finding_id,matter_id,revision_id,historical,request))
