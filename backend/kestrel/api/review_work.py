from fastapi import APIRouter,Depends,Request
from pydantic import BaseModel,ConfigDict
from kestrel.api.auth import identity,database
from kestrel.schemas.review_work import TaskCreate,TaskEvent,CustodianCreate,PartyCreate,Reason
from kestrel.services import review_work as s
router=APIRouter(prefix='/api/v1/review-work',tags=['Custodians, parties and parallel review tasks'])

@router.get('/sources/{source_id}')
def panel(source_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    source,_=s.source(db,actor[2],source_id)
    return protected(db,request,actor[2],source.matter_id,'review.panel',lambda fresh:s.source_panel(db,fresh,source_id))

@router.get('/sources/{source_id}/eligible-people')
def people(source_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    source,_=s.source(db,actor[2],source_id)
    return protected(db,request,actor[2],source.matter_id,'review.people',lambda fresh:s.eligible_people(db,fresh,source_id))

@router.post('/sources/{source_id}/custodians',status_code=201)
def custodian(source_id:str,payload:CustodianCreate,actor=Depends(identity),db=Depends(database)):return s.create_custodian(db,actor[2],source_id,payload)

@router.post('/custodian-links/{link_id}/retire',status_code=201)
def retire(link_id:str,payload:Reason,actor=Depends(identity),db=Depends(database)):return s.retire_custodian(db,actor[2],link_id,payload)

@router.post('/sources/{source_id}/parties',status_code=201)
def party(source_id:str,payload:PartyCreate,actor=Depends(identity),db=Depends(database)):return s.create_party(db,actor[2],source_id,payload)

@router.post('/sources/{source_id}/tasks',status_code=201)
def create(source_id:str,payload:TaskCreate,actor=Depends(identity),db=Depends(database)):return s.create_task(db,actor[2],source_id,payload)

@router.get('/tasks/{task_id}')
def get(task_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    initial,_=s.task_row(db,actor[2],task_id)
    def prepare(fresh):
        row,history=s.task_row(db,fresh,task_id);value=s.task_output(db,fresh,row)
        _,policy=s.source(db,fresh,row.source_id)
        s.audit_work(db,fresh,policy,'review.task.view',row,history);db.commit();return value
    return protected(db,request,actor[2],initial.matter_id,'review.task',prepare)

@router.post('/tasks/{task_id}/events',status_code=201)
def event(task_id:str,payload:TaskEvent,actor=Depends(identity),db=Depends(database)):return s.transition(db,actor[2],task_id,payload)

@router.get('/notifications')
def notifications(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    return protected(db,request,actor[2],matter_id,'review.notifications',lambda fresh:s.notifications(db,fresh,matter_id))

class Empty(BaseModel):
    model_config=ConfigDict(extra='forbid')

@router.post('/notifications/{notification_id}/read')
def acknowledge(notification_id:str,payload:Empty,actor=Depends(identity),db=Depends(database)):return s.acknowledge(db,actor[2],notification_id)
