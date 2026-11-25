from fastapi import APIRouter,Depends,HTTPException,Request
from kestrel.api.auth import identity,database
from kestrel.schemas.financial import Fact,Decision,Gate,Query,Compare,Resolution
from kestrel.services import financial as s
router=APIRouter(prefix='/api/v1/financial',tags=['Evidence-bound financial facts'])

@router.get('/organization-gate')
def organization_gate(actor=Depends(identity),db=Depends(database)):return s.organization_gate(db,actor[2])
@router.post('/organization-gate')
def configure_organization(payload:Gate,actor=Depends(identity),db=Depends(database)):return s.organization_gate(db,actor[2],payload)
def execute(db,actor,operation,call):
    try:return call()
    except HTTPException as error:
        if error.status_code==403:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'financial.'+operation+'.denied','denied',actor.id,category='access');db.commit()
        raise
@router.post('/facts',status_code=201)
def propose(payload:Fact,actor=Depends(identity),db=Depends(database)):return execute(db,actor[2],'propose',lambda:s.propose(db,actor[2],payload))
@router.post('/facts/{fact_id}/decisions')
def decide(fact_id:str,payload:Decision,actor=Depends(identity),db=Depends(database)):return execute(db,actor[2],'decision',lambda:s.decide(db,actor[2],fact_id,payload))
@router.post('/query')
def query(payload:Query,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    return protected(db,request,actor[2],payload.matter_id,'financial.query',lambda fresh:s.query(db,fresh,payload))
@router.post('/compare')
def compare(payload:Compare,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel import models as m
    from kestrel.services.response_guard import protected
    fact=db.get(m.FinancialFact,payload.left_id)
    if not fact:raise HTTPException(404,'Financial evidence unavailable')
    return protected(db,request,actor[2],fact.matter_id,'financial.compare',lambda fresh:s.reconcile(db,fresh,payload))
@router.post('/reconciliations/{case_id}/resolve')
def resolve(case_id:str,payload:Resolution,actor=Depends(identity),db=Depends(database)):return execute(db,actor[2],'resolve',lambda:s.resolve(db,actor[2],case_id,payload))
@router.get('/reconciliations')
def cases(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    return protected(db,request,actor[2],matter_id,'financial.cases',lambda fresh:s.cases(db,fresh,matter_id))
@router.get('/bank-gate')
def gate(matter_id:str,actor=Depends(identity),db=Depends(database)):return execute(db,actor[2],'gate',lambda:s.gate(db,actor[2],matter_id))
@router.post('/bank-gate')
def configure(matter_id:str,payload:Gate,actor=Depends(identity),db=Depends(database)):return execute(db,actor[2],'configure',lambda:s.gate(db,actor[2],matter_id,payload))
