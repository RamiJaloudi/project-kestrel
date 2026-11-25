from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from kestrel.api.auth import identity,database
from kestrel.schemas.table_views import Create,Version,Share,ShareDecision
from kestrel.services import table_views as s,data_tables as tables

router=APIRouter(prefix='/api/v1/table-views',tags=['Retained private and independently shared table configurations'])

def execute(db,actor,request,matter,dataset,operation,call,validate=None):
    try:
        tables.throttle(actor);before,actor=tables.begin(db,request,matter);s.scope(db,actor,matter,dataset)
        value=call(actor)
        if operation in {'create','version','share_request','decision'}:
            # These operations intentionally add retained authorization records.
            # Recheck current identity and exact returned evidence without treating
            # our own writes as a concurrent third-party policy mutation.
            from kestrel.services.auth import authenticate
            db.expire_all();actor=authenticate(db,request)[2]
        else:actor=tables.finish(db,request,matter,before)
        s.scope(db,actor,matter,dataset)
        if validate:validate(actor,value)
        return value
    except HTTPException as error:
        if error.status_code in {401,403,409}:
            db.rollback()
            from kestrel.services.auth import audit
            audit(db,'table_view.'+operation+'.denied','denied',actor.id,category='access');db.commit()
        raise

def config_check(db,actor,value):
    view=s.row(db,value['id']);version=s.authorized_version(db,actor,view)
    if version.content_hash!=value['version_hash']:raise HTTPException(409,'Saved configuration changed while preparing response')
    s.bound(db,actor,version)

@router.get('')
def listing(matter_id:str,dataset:Literal['inventory','financial'],request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,actor[2],request,matter_id,dataset,'list',lambda a:s.listing(db,a,matter_id,dataset),lambda a,v:[config_check(db,a,item) for item in v])

@router.post('',status_code=201)
def create(payload:Create,request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,actor[2],request,payload.matter_id,payload.dataset,'create',lambda a:s.create(db,a,payload),lambda a,v:config_check(db,a,v))

@router.get('/recipients')
def recipients(matter_id:str,dataset:Literal['inventory','financial'],request:Request,actor=Depends(identity),db=Depends(database)):
    return execute(db,actor[2],request,matter_id,dataset,'recipients',lambda a:s.eligible_people(db,a,matter_id,dataset))

@router.get('/share-requests')
def queue(matter_id:str,dataset:Literal['inventory','financial'],request:Request,actor=Depends(identity),db=Depends(database)):
    def validate(a,items):
        for item in items:
            share=db.get(s.m.TableViewShare,item['id']);version=db.get(s.m.TableViewVersion,share.version_id);s.request_output(db,a,s.row(db,version.view_id),version,share)
    return execute(db,actor[2],request,matter_id,dataset,'review_queue',lambda a:s.review_queue(db,a,matter_id,dataset),validate)

@router.post('/share-requests/{share_id}/decisions')
def decide(share_id:str,payload:ShareDecision,request:Request,actor=Depends(identity),db=Depends(database)):
    share=db.get(s.m.TableViewShare,share_id)
    if not share:raise HTTPException(404,'Share request unavailable')
    version=db.get(s.m.TableViewVersion,share.version_id);view=s.row(db,version.view_id)
    return execute(db,actor[2],request,view.matter_id,view.dataset,'decision',lambda a:s.decide(db,a,share_id,payload))

@router.get('/{view_id}')
def get(view_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    view=s.row(db,view_id)
    return execute(db,actor[2],request,view.matter_id,view.dataset,'read',lambda a:s.get(db,a,view_id),lambda a,v:config_check(db,a,v))

@router.post('/{view_id}/versions',status_code=201)
def version(view_id:str,payload:Version,request:Request,actor=Depends(identity),db=Depends(database)):
    view=s.row(db,view_id)
    return execute(db,actor[2],request,view.matter_id,view.dataset,'version',lambda a:s.update(db,a,view_id,payload),lambda a,v:config_check(db,a,v))

@router.post('/{view_id}/share-requests',status_code=201)
def share(view_id:str,payload:Share,request:Request,actor=Depends(identity),db=Depends(database)):
    view=s.row(db,view_id)
    def validate(a,value):
        stored=db.get(s.m.TableViewShare,value['id']);v=db.get(s.m.TableViewVersion,stored.version_id);s.request_output(db,a,view,v,stored)
    return execute(db,actor[2],request,view.matter_id,view.dataset,'share_request',lambda a:s.request_share(db,a,view_id,payload),validate)
