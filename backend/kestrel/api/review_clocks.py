from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from kestrel.api.auth import identity,database
from kestrel.schemas.review_clocks import CalendarCreate,PolicyCreate,PolicyDecision,SlaBind,SessionBegin,SessionReceipt
from kestrel.services import review_clocks as c
router=APIRouter(prefix='/api/v1/review-clocks',tags=['Reader timing and approved operational SLA'])

@router.get('/configuration')
def configuration(matter_id:str,actor=Depends(identity),db=Depends(database)):return c.configuration(db,actor[2],matter_id)
@router.post('/calendars',status_code=201)
def calendar(payload:CalendarCreate,actor=Depends(identity),db=Depends(database)):return c.create_calendar(db,actor[2],payload)
@router.post('/policies',status_code=201)
def policy(payload:PolicyCreate,actor=Depends(identity),db=Depends(database)):return c.create_policy(db,actor[2],payload)
@router.post('/policies/{policy_id}/{operation}')
def decision(policy_id:str,operation:Literal['submit','approve','reject','publish'],payload:PolicyDecision,actor=Depends(identity),db=Depends(database)):return c.decide_policy(db,actor[2],policy_id,operation,payload)
@router.post('/tasks/{task_id}/sla',status_code=201)
def bind(task_id:str,payload:SlaBind,actor=Depends(identity),db=Depends(database)):return c.bind(db,actor[2],task_id,payload)
@router.post('/tasks/{task_id}/sessions',status_code=201)
def begin(task_id:str,payload:SessionBegin,actor=Depends(identity),db=Depends(database)):return c.begin(db,actor[2],task_id,payload)
@router.get('/sessions/{session_id}')
def session(session_id:str,actor=Depends(identity),db=Depends(database)):
    c.rw.internal(actor[2]);s=db.get(c.m.ReviewSession,session_id)
    if not s or (s.account_id!=actor[2].id and c.R.AUDITOR not in actor[2].roles):raise HTTPException(403,'Own session or designated scoped auditor required')
    c.rw.task_row(db,actor[2],s.task_id);return c.session_output(db,actor[2],s)
@router.post('/sessions/{session_id}/receipts',status_code=201)
def receipt(session_id:str,payload:SessionReceipt,actor=Depends(identity),db=Depends(database)):return c.receipt(db,actor[2],session_id,payload)
