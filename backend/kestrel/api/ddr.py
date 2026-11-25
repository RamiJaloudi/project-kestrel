"""No generic checkpoint/thread API; all commands use authenticated server identity."""
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from kestrel import models as m
from kestrel.api.auth import identity,database
from kestrel.schemas.ddr_runs import Create,Review,Command
from kestrel.services import ddr_runs as s,data_tables as tables,workflow as w,diligence
router=APIRouter(prefix='/api/v1/ddr',tags=['Governed internal DDR runs'])


def checked(db,actor,request,matter,operation,call):
    try:
        before,fresh=tables.begin(db,request,matter);w.legal(fresh,matter)
        value=call(fresh)
        # Command services commit authorized writes. Their exact content is
        # independently validated; read responses also detect concurrent drift.
        if operation in {'list','read','options'}:tables.finish(db,request,matter,before)
        else:
            from kestrel.services.auth import authenticate
            db.expire_all();fresh=authenticate(db,request)[2];w.legal(fresh,matter)
            if isinstance(value,dict) and value.get('id'):s.read(db,fresh,value['id'])
        return value
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'ddr.'+operation+'.denied','denied',actor.id,category='access');db.commit()
        raise


@router.post('/matters/{matter_id}/runs',status_code=201)
def create(matter_id:str,p:Create,request:Request,actor=Depends(identity),db=Depends(database)):
    if p.matter_id!=matter_id:raise HTTPException(422,'Matter path and request must match')
    return checked(db,actor[2],request,matter_id,'create',lambda a:s.output(db,a,s.create(db,a,p),True))


@router.get('/matters/{matter_id}/runs')
def listing(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    def visible(a):
        result=[]
        for run in db.scalars(select(m.DDRRun).where(m.DDRRun.matter_id==matter_id).order_by(m.DDRRun.created_at.desc()).limit(101)):
            try:result.append(s.output(db,a,run))
            except HTTPException as error:
                if error.status_code not in {403,404}:raise
        if len(result)>100:raise HTTPException(413,'More than100 permitted runs; narrow the workspace before continuing')
        return result
    return checked(db,actor[2],request,matter_id,'list',visible)


@router.get('/matters/{matter_id}/evidence-options')
def options(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    def permitted(a):
        findings=[f for f in diligence.visible_findings(db,a,matter_id,audited=False) if f['review_state']=='reviewed']
        books=[]
        for book in db.scalars(select(m.GovernanceVersion).where(m.GovernanceVersion.matter_id==matter_id,m.GovernanceVersion.kind=='legal_playbook',m.GovernanceVersion.state=='published')):
            try:s.configuration(db,a,matter_id,book.id,'offline');books.append({'id':book.id,'name':book.name})
            except HTTPException:continue
        from kestrel.services.agent_registry import eligible_version
        profiles=[]
        for version in db.scalars(select(m.AgentProfileVersion).where(m.AgentProfileVersion.matter_id==matter_id)):
            try:
                definition=eligible_version(db,version)
                profiles.append({'id':version.id,'name':db.get(m.AgentProfile,version.profile_id).name,'agent_kind':definition.agent_kind,'provider':definition.provider})
            except HTTPException:continue
        return {'findings':[{'id':f['id'],'summary':f['summary'],'source':f['file_name'],'playbook_id':f['playbook_id']} for f in findings], 'playbooks':books,'agent_profiles':profiles,'live_enabled':s.live_availability()}
    return checked(db,actor[2],request,matter_id,'options',permitted)


@router.get('/runs/{run_id}')
def get(run_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    run=s.row(db,run_id)
    return checked(db,actor[2],request,run.matter_id,'read',lambda a:s.output(db,a,s.read(db,a,run_id),True))


@router.post('/runs/{run_id}/cancel')
def cancel(run_id:str,p:Command,request:Request,actor=Depends(identity),db=Depends(database)):
    run=s.row(db,run_id)
    return checked(db,actor[2],request,run.matter_id,'cancel',lambda a:s.output(db,a,s.cancel(db,a,run_id,p.rationale),True))


@router.post('/tasks/{task_id}/decisions')
def decide(task_id:str,p:Review,request:Request,actor=Depends(identity),db=Depends(database)):
    task=db.get(m.DDRTask,task_id)
    if not task:raise HTTPException(404,'Internal task unavailable')
    def apply(a):s.decide(db,a,task_id,p);return s.output(db,a,s.read(db,a,task.run_id),True)
    return checked(db,actor[2],request,task.matter_id,'decision',apply)


@router.post('/agent-impacts/{task_id}/rerun',status_code=201)
def rerun(task_id:str,p:Command,request:Request,actor=Depends(identity),db=Depends(database)):
    task=db.get(m.AgentProfileImpactTask,task_id)
    if not task:raise HTTPException(404,'Impact task unavailable')
    return checked(db,actor[2],request,task.matter_id,'rerun',lambda a:s.output(db,a,s.rerun_impact(db,a,task_id,p.rationale),True))
