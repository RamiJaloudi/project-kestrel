from fastapi import APIRouter,Depends,Request,HTTPException
from kestrel.api.auth import identity,database
from kestrel.schemas.intelligence import IntelligenceQuery,ProfileCreate,GovernedDecision,OverrideCreate,AlertDisposition
from kestrel.schemas.review_work import Reason,Input
from kestrel.services import intelligence as s
from kestrel.services import intelligence_governance as g
from kestrel.services import data_tables as tables,review_work as rw,workflow as w,review_clocks as clocks
from kestrel.services.auth import authenticate,audit
from kestrel.domain import Organization as O,Role as R
from kestrel import models as m

router=APIRouter(prefix='/api/v1/intelligence',tags=['Authorized review intelligence'])


def current(db,request):
    db.expire_all();actor=authenticate(db,request)[2]
    if actor.org!=O.FIRM:raise HTTPException(403,'Internal intelligence governance required')
    return actor


def guarded(db,request,initial,scope,prepare,recheck,*,stamp=False):
    """Governance metadata can allow scoped root configuration, never source bypass.

    Read stamps detect hidden retained-scope changes as well as current source
    changes. Actions recheck their exact current capability without comparing an
    input stamp that their own authorized immutable write necessarily changed.
    """
    try:
        actor=current(db,request);matter=scope(actor)
        before=tables.authorization_inputs(db,matter,actor.id) if stamp else None
        result=prepare(actor)
        fresh=current(db,request);recheck(fresh,result)
        if stamp and tables.authorization_inputs(db,matter,fresh.id)!=before:raise HTTPException(409,'Authorization changed while preparing intelligence; refresh before retrying')
        return result
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback();audit(db,'intelligence.governance.response_denied','denied',initial.id,category='access');db.commit()
        raise


def profile_scope(db,actor,pid):return g.profile_read(db,actor,pid).matter_id


def configuration_scope(db,actor,matter,people=False):
    if people:clocks.config_access(db,actor,matter)
    else:g.access(actor,matter,db=db)
    return matter


def source_matter_scope(actor,matter):
    w.legal(actor,matter);return matter


def override_scope(db,actor,oid):
    row=db.get(m.IntelligenceOverride,oid)
    if not row:raise HTTPException(404,'Override unavailable')
    return g.override_read(db,actor,row)[0].matter_id


def profile_decision_check(db,actor,pid,operation):
    row=g.profile_read(db,actor,pid)
    if operation in {'approve','reject','revoke'}:
        if R.SME not in actor.roles or actor.id==row.author_id:raise HTTPException(403,'Independent scoped SME required')
    elif not actor.roles&{R.ROOT_ADMIN,R.SME}:raise HTTPException(403,'Scoped configuration role required')


def override_check(db,actor,oid,decision=False):
    row=db.get(m.IntelligenceOverride,oid)
    if not row:raise HTTPException(404,'Override unavailable')
    if decision and (R.SME not in actor.roles or actor.id==row.created_by):raise HTTPException(403,'Independent source-cleared SME required')
    g.override_output(db,actor,row)


@router.post('/query')
def query(payload:IntelligenceQuery,request:Request,actor=Depends(identity),db=Depends(database)):
    try:return s.query(db,actor[2],payload,request)
    except HTTPException as error:
        if error.status_code==403:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'intelligence.query.denied','denied',actor[2].id,category='access');db.commit()
        raise


@router.get('/profiles')
def profiles(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    return guarded(db,request,actor[2],lambda fresh:configuration_scope(db,fresh,matter_id),lambda fresh:g.profiles(db,fresh,matter_id),lambda fresh,result:g.access(fresh,matter_id,db=db),stamp=True)

@router.get('/profiles/people')
def profile_people(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    return guarded(db,request,actor[2],lambda fresh:configuration_scope(db,fresh,matter_id,True),lambda fresh:g.configuration_people(db,fresh,matter_id),lambda fresh,result:clocks.config_access(db,fresh,matter_id),stamp=True)

@router.post('/profiles',status_code=201)
def create_profile(payload:ProfileCreate,request:Request,actor=Depends(identity),db=Depends(database)):
    def check(fresh,result):clocks.config_access(db,fresh,payload.matter_id);g.profile_read(db,fresh,result['id'])
    return guarded(db,request,actor[2],lambda fresh:payload.matter_id,lambda fresh:g.create_profile(db,fresh,payload),check)

@router.post('/profiles/{profile_id}/decisions')
def decide_profile(profile_id:str,payload:GovernedDecision,request:Request,actor=Depends(identity),db=Depends(database)):
    return guarded(db,request,actor[2],lambda fresh:profile_scope(db,fresh,profile_id),lambda fresh:g.decide_profile(db,fresh,profile_id,payload),lambda fresh,result:profile_decision_check(db,fresh,profile_id,payload.operation))

@router.post('/profiles/{profile_id}/scan')
def scan(profile_id:str,payload:Reason,request:Request,actor=Depends(identity),db=Depends(database)):
    def check(fresh,result):row=g.profile_read(db,fresh,profile_id,True);w.legal(fresh,row.matter_id)
    return guarded(db,request,actor[2],lambda fresh:profile_scope(db,fresh,profile_id),lambda fresh:g.scan(db,fresh,profile_id,payload),check,stamp=True)

@router.post('/overrides',status_code=201)
def create_override(payload:OverrideCreate,request:Request,actor=Depends(identity),db=Depends(database)):
    return guarded(db,request,actor[2],lambda fresh:rw.source(db,fresh,payload.source_id)[0].matter_id,lambda fresh:g.create_override(db,fresh,payload),lambda fresh,result:override_check(db,fresh,result['id']))

@router.get('/overrides')
def overrides(source_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    def check(fresh,result):
        rw.source(db,fresh,source_id)
        for row in result:override_check(db,fresh,row['id'])
    return guarded(db,request,actor[2],lambda fresh:rw.source(db,fresh,source_id)[0].matter_id,lambda fresh:g.overrides(db,fresh,source_id),check,stamp=True)

@router.post('/overrides/{override_id}/decisions')
def decide_override(override_id:str,payload:GovernedDecision,request:Request,actor=Depends(identity),db=Depends(database)):
    return guarded(db,request,actor[2],lambda fresh:override_scope(db,fresh,override_id),lambda fresh:g.decide_override(db,fresh,override_id,payload),lambda fresh,result:override_check(db,fresh,override_id,True))

@router.get('/alerts')
def alerts(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    def check(fresh,result):
        w.legal(fresh,matter_id)
        for row in result:g.alert_output(db,fresh,g.alert_access(db,fresh,row['id']))
    return guarded(db,request,actor[2],lambda fresh:source_matter_scope(fresh,matter_id),lambda fresh:g.inbox(db,fresh,matter_id),check,stamp=True)

@router.post('/alerts/{alert_id}/read')
def read_alert(alert_id:str,payload:Input,request:Request,actor=Depends(identity),db=Depends(database)):
    return guarded(db,request,actor[2],lambda fresh:g.alert_access(db,fresh,alert_id).matter_id,lambda fresh:g.read_alert(db,fresh,alert_id),lambda fresh,result:g.alert_access(db,fresh,alert_id))

@router.post('/alerts/{alert_id}/dispositions')
def disposition(alert_id:str,payload:AlertDisposition,request:Request,actor=Depends(identity),db=Depends(database)):
    def check(fresh,result):
        row=g.alert_access(db,fresh,alert_id)
        if payload.operation=='close' and fresh.id!=row.created_by and R.SME not in fresh.roles:raise HTTPException(403,'Alert creator or current SME required')
        g.alert_output(db,fresh,row)
    return guarded(db,request,actor[2],lambda fresh:g.alert_access(db,fresh,alert_id).matter_id,lambda fresh:g.disposition(db,fresh,alert_id,payload),check)
