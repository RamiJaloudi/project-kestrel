from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel import models as m
from kestrel.api.auth import identity,database
from kestrel.domain import Role as R,Organization as O
from kestrel.services import action_center as service
from kestrel.services.auth import audit,clock

router=APIRouter(prefix='/api/v1/action-center',tags=['Legal SME Action Center'])


class Empty(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Claim(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(default='',max_length=1000)


class Reason(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(min_length=5,max_length=1000)


class Decision(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    snapshot_hash:str=Field(pattern=r'^[a-f0-9]{64}$')
    rationale:str=Field(min_length=5,max_length=1000)
    idempotency_key:str=Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')
    engine_name:Literal['literal','openai']='literal'


class Disposition(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    disposition:Literal['accept_reviewed_candidate','retain_prior','no_change','not_redetected_reviewed']
    rationale:str=Field(min_length=5,max_length=1000)


class Closure(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(min_length=5,max_length=1000)
    release_handling_rationale:str=Field(default='',max_length=1000)


def legal(actor):
    if actor.org!=O.FIRM or not actor.roles&{R.SME,R.LAWYER,R.ANTITRUST}:raise HTTPException(403,'Internal legal role required')


@router.get('/tasks')
def tasks(matter_id:str|None=None,actor=Depends(identity),db=Depends(database)):
    legal(actor[2]);query=select(m.GovernanceTask).join(m.ImpactSnapshot,m.GovernanceTask.impact_id==m.ImpactSnapshot.id)
    if matter_id:query=query.where(m.ImpactSnapshot.matter_id==matter_id)
    result=[]
    for task in db.scalars(query.order_by(m.GovernanceTask.created_at.desc(),m.GovernanceTask.id)):
        try:
            result.append(service.output(db,actor[2],task,detail=False))
            _,_,_,policy=service.access(db,actor[2],task.id)
            service.w.event(db,actor[2],policy,'impact.list',task.id)
        except HTTPException as error:
            if error.status_code!=403:raise
    db.commit()
    return result


@router.get('/tasks/{task_id}')
def task(task_id:str,actor=Depends(identity),db=Depends(database)):
    task,impact,_,policy=service.access(db,actor[2],task_id)
    result=service.output(db,actor[2],task)
    service.w.event(db,actor[2],policy,'impact.view',task_id)
    for comparison in result['comparisons']:
        for side in ['old','new']:
            finding=comparison[side]
            if finding:
                row=db.get(m.LegalFindingRevision,finding['revision_id']) or db.get(m.SourceFinding,finding['revision_id'])
                service.w.event(db,actor[2],db.get(m.DocumentPolicyVersion,row.policy_id),'finding.view',row.id)
    db.commit()
    return result


@router.post('/tasks/{task_id}/claim')
def claim(task_id:str,payload:Claim,actor=Depends(identity),db=Depends(database)):
    return service.output(db,actor[2],service.claim(db,actor[2],task_id,payload.rationale))


@router.post('/tasks/{task_id}/return-claim')
def return_claim(task_id:str,payload:Reason,actor=Depends(identity),db=Depends(database)):
    return service.output(db,actor[2],service.return_claim(db,actor[2],task_id,payload.rationale))


@router.post('/tasks/{task_id}/reassess')
def reassess(task_id:str,payload:Empty,actor=Depends(identity),db=Depends(database)):
    return service.output(db,actor[2],service.refresh(db,actor[2],task_id))


@router.post('/comparisons/{comparison_id}/disposition')
def disposition(comparison_id:str,payload:Disposition,actor=Depends(identity),db=Depends(database)):
    service.disposition(db,actor[2],comparison_id,payload)
    return {'status':'recorded'}


@router.post('/tasks/{task_id}/close')
def close(task_id:str,payload:Closure,actor=Depends(identity),db=Depends(database)):
    return service.output(db,actor[2],service.close(db,actor[2],task_id,payload))


@router.get('/publications')
def publications(actor=Depends(identity),db=Depends(database)):
    legal(actor[2]);return service.publications(db,actor[2])


@router.post('/publications/{publication_id}/retry')
def retry_publication(publication_id:str,payload:Empty,actor=Depends(identity),db=Depends(database)):
    service.recover_publication(db,actor[2],publication_id)
    return {'status':'pending'}


@router.get('/notifications')
def notifications(actor=Depends(identity),db=Depends(database)):
    legal(actor[2]);result=[]
    for notice in db.scalars(select(m.TaskNotification).where(m.TaskNotification.account_id==actor[0].id).order_by(m.TaskNotification.created_at.desc(),m.TaskNotification.id)):
        try:task,_,_,_=service.access(db,actor[2],notice.task_id)
        except HTTPException as error:
            if error.status_code==403:continue
            raise
        result.append({'id':notice.id,'task_id':notice.task_id,'state':notice.state,'created_at':notice.created_at,'escalated_at':notice.escalated_at,'title':'Legal change-impact task','priority':task.priority,'task_state':task.state,'overdue':task.due_at<clock() and task.state not in {'closed','rejected','superseded'}})
    return result


@router.post('/notifications/{notification_id}/{operation}')
def notification(notification_id:str,operation:Literal['read','acknowledge','resolve'],payload:Empty,actor=Depends(identity),db=Depends(database)):
    notice=db.scalar(select(m.TaskNotification).where(m.TaskNotification.id==notification_id,m.TaskNotification.account_id==actor[0].id).with_for_update())
    if notice is None:raise HTTPException(404,'Notification unavailable')
    task,impact,_,_=service.access(db,actor[2],notice.task_id)
    if operation=='resolve' and task.state not in {'closed','rejected','superseded'}:raise HTTPException(409,'Task remains outstanding')
    rank={'unread':0,'read':1,'acknowledged':2,'resolved':3};target={'read':'read','acknowledge':'acknowledged','resolve':'resolved'}[operation]
    if rank[target]>rank[notice.state]:notice.state=target
    service.record(db,impact.source_id,'notification.'+operation,'allowed',notice.id,actor[0].id);db.commit()
    return {'id':notice.id,'state':notice.state,'task_id':task.id}


@router.post('/tasks/{task_id}/{operation}')
def decide(task_id:str,operation:Literal['approve','reject'],payload:Decision,actor=Depends(identity),db=Depends(database)):
    return service.output(db,actor[2],service.decide(db,actor[2],task_id,operation,payload))


