from typing import Literal
from fastapi import APIRouter,Depends
from kestrel.api.auth import identity,database
from kestrel.schemas.gate1_completion import EscalationPlan,EscalationDecision,AlertDisposition
from kestrel.services import sla_alerts as s
router=APIRouter(prefix='/api/v1/sla-alerts',tags=['Scoped operational SLA alerts'])
@router.get('')
def inbox(matter_id:str,actor=Depends(identity),db=Depends(database)):return s.inbox(db,actor[2],matter_id)
@router.get('/tasks/{task_id}/plans')
def plans(task_id:str,actor=Depends(identity),db=Depends(database)):return s.plans(db,actor[2],task_id)
@router.post('/tasks/{task_id}/plans',status_code=201)
def propose(task_id:str,payload:EscalationPlan,actor=Depends(identity),db=Depends(database)):return s.propose(db,actor[2],task_id,payload)
@router.post('/plans/{plan_id}/{operation}')
def decide(plan_id:str,operation:Literal['approve','reject'],payload:EscalationDecision,actor=Depends(identity),db=Depends(database)):return s.decide(db,actor[2],plan_id,operation,payload)
@router.post('/{alert_id}/read')
def read(alert_id:str,actor=Depends(identity),db=Depends(database)):return s.read(db,actor[2],alert_id)
@router.post('/{alert_id}/dispositions',status_code=201)
def disposition(alert_id:str,payload:AlertDisposition,actor=Depends(identity),db=Depends(database)):return s.disposition(db,actor[2],alert_id,payload)
