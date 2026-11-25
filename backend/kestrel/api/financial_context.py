"""Internal sidecars; no context/candidate is added to released financial JSON."""
from fastapi import APIRouter,Depends,HTTPException,Request
from kestrel.api.auth import identity,database
from kestrel.schemas.financial_context import Create,Decision,Compare,Scan
from kestrel.services import financial_context as s,data_tables as tables
from kestrel.adapters.extraction import canonical
router=APIRouter(prefix='/api/v1/financial-context',tags=['Internal financial context and unapproved staging'])

def execute(db,request,actor,matter,operation,prepare,validate):
    try:
        before,fresh=tables.begin(db,request,matter);s.internal(fresh)
        with db.no_autoflush:value=prepare(fresh)
        fresh=tables.finish(db,request,matter,before);s.internal(fresh)
        # Sidecar decisions and their independent reviewers are re-resolved
        # after source authorization. They are intentionally not global PDP
        # change inputs: append-only writes must not invalidate themselves.
        with db.no_autoflush:checked=validate(fresh,value)
        if canonical(checked)!=canonical(value):raise HTTPException(409,'Financial context changed while preparing response; refresh exact versions')
        db.commit()
        return value
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'financial_context.'+operation+'.denied','denied',actor.id,category='access');db.commit()
        raise

def fact_matter(db,fid):
    row=db.get(s.m.FinancialFact,fid)
    if not row:raise HTTPException(404,'Financial fact unavailable')
    return row.matter_id

def context_matter(db,cid):
    row=db.get(s.m.FinancialFactContext,cid)
    if not row:raise HTTPException(404,'Financial context unavailable')
    return row.matter_id

def source_matter(db,sid):
    row=db.get(s.m.SourceVersion,sid)
    if not row:raise HTTPException(404,'Source unavailable')
    return row.matter_id

@router.get('/facts/{fact_id}')
def get(fact_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,request,actor[2],fact_matter(db,fact_id),'read',lambda a:s.fact_view(db,a,fact_id),lambda a,v:s.fact_view(db,a,fact_id))

@router.post('/facts/{fact_id}/versions',status_code=201)
def propose(fact_id:str,payload:Create,request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,request,actor[2],fact_matter(db,fact_id),'propose',lambda a:s.propose(db,a,fact_id,payload),lambda a,v:s.output(db,a,db.get(s.m.FinancialFactContext,v['id'])))

@router.post('/versions/{context_id}/decisions')
def decide(context_id:str,payload:Decision,request:Request,actor=Depends(identity),db=Depends(database)):
    def receipt(a,value):
        context=db.get(s.m.FinancialFactContext,context_id)
        return {'id':context_id,'content_hash':context.content_hash,'state':s.state(db,context),'audience':'internal_only'}
    return execute(db,request,actor[2],context_matter(db,context_id),'decision',lambda a:s.decide(db,a,context_id,payload),receipt)

@router.post('/compare')
def compare(payload:Compare,request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,request,actor[2],payload.matter_id,'compare',lambda a:s.comparison(db,a,payload),lambda a,v:s.comparison(db,a,payload))

@router.get('/sources/{source_id}/candidates')
def candidates(source_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,request,actor[2],source_matter(db,source_id),'candidates',lambda a:s.candidate_list(db,a,source_id),lambda a,v:s.candidate_list(db,a,source_id))

@router.post('/sources/{source_id}/scan',status_code=201)
def scan(source_id:str,payload:Scan,request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,request,actor[2],source_matter(db,source_id),'stage',lambda a:s.scan(db,a,source_id,payload),lambda a,v:[s.candidate_output(db,a,item['id']) for item in v])
