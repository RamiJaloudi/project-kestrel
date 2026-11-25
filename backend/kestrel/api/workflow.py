from typing import Annotated,Literal
from urllib.parse import quote
from fastapi import APIRouter,Depends,Request,Query,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import SourceFinding,DocumentPolicyVersion as Policy,ReleasePackage,Matter,MatterValidation,Client,GovernanceVersion
from kestrel.domain import Organization as O
from kestrel.domain import Role as R
from kestrel.services import workflow as service
from kestrel.adapters.extraction import MAX_BYTES
from starlette.concurrency import run_in_threadpool

router=APIRouter(prefix='/api/v1/workflow',tags=['Document review and audience release'])

@router.get('/ai-status')
def ai_status(actor=Depends(identity),db=Depends(database)):
    if actor[2].org!=O.FIRM or not actor[2].roles&{R.SME,R.ROOT_ADMIN}:raise HTTPException(403,'AI administration role required')
    from kestrel.services.ai_budget import status
    from kestrel.adapters.openai_review import configuration,MODEL
    enabled,key=configuration()
    return {**status(db),'enabled':enabled,'key_configured':bool(key),'model':MODEL}

class UploadMeta(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(max_length=36)
    file_name:str=Field(min_length=1,max_length=160)
    logical_key:str=Field(min_length=1,max_length=96,pattern=r'^[A-Za-z0-9_-]+$')
    classification:Literal['ordinary','privileged','clean_team']
    resource_type:Literal['contract','licence','pricing','financial','legal_advice','client_upload','tracker','report']='contract'
    clean_team_scope:str=Field(default='',max_length=128)
    language:Literal['en','de','unknown']='unknown'
    governing_law:str=Field(default='unconfirmed',min_length=1,max_length=80)
    wave:Literal['wave1','wave2','manual']='manual'
    previous_id:str | None=Field(default=None,max_length=36)
    import_row_id:str | None=Field(default=None,max_length=36)
    synthetic:bool=False

class Reason(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    rationale:str=Field(min_length=5,max_length=1000)

class Confirm(Reason):
    snapshot_hash:str=Field(min_length=64,max_length=64)

class Classification(Confirm):
    classification:Literal['ordinary','privileged','clean_team']
    resource_type:Literal['contract','licence','pricing','financial','legal_advice','client_upload','tracker','report']

class Review(Reason):
    decision:Literal['reviewed','rejected']

class Reference(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    finding_id:str=Field(max_length=36)
    revision_id:str | None=Field(default=None,max_length=36)
    public_reference:str=Field(min_length=3,max_length=160)

class Package(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(max_length=36)
    audience:Literal['halden','castlegate']
    title:str=Field(min_length=3,max_length=160)
    summary:str=Field(min_length=10,max_length=6000)
    references:list[Reference]=Field(min_length=1,max_length=30)

class Approval(Reason):
    content_hash:str=Field(min_length=64,max_length=64)
    snapshot_hash:str=Field(min_length=64,max_length=64)

@router.get('/matters')
def matters(actor=Depends(identity),db=Depends(database)):
    return [dict(row) for row in db.execute(select(Matter.id,Matter.name,Client.client_number,MatterValidation.matter_number)
        .join(MatterValidation,MatterValidation.matter_id==Matter.id).join(Client,Client.id==MatterValidation.client_id)
        .where(Matter.id.in_(actor[2].matters-actor[2].walls))).mappings()]

@router.get('/playbooks')
def playbooks(matter_id:str,actor=Depends(identity),db=Depends(database)):
    service.legal(actor[2],matter_id)
    return [{'id':r.id,'name':r.name,'content_hash':r.content_hash} for r in db.scalars(select(GovernanceVersion).where(
        GovernanceVersion.matter_id==matter_id,GovernanceVersion.kind=='legal_playbook',GovernanceVersion.state=='published'))]

@router.post('/documents',status_code=201,openapi_extra={'requestBody':{'required':True,'content':{'application/octet-stream':{'schema':{'type':'string','format':'binary'}}}}})
async def upload(request:Request,meta:Annotated[UploadMeta,Query()],actor=Depends(identity),db=Depends(database)):
    service.legal(actor[2],meta.matter_id)
    if not meta.synthetic:raise HTTPException(422,'Confirm synthetic source material')
    if request.headers.get('content-type','').split(';')[0]!='application/octet-stream':raise HTTPException(415,'Send a binary file body')
    data=bytearray()
    async for chunk in request.stream():
        if len(data)+len(chunk)>MAX_BYTES:raise HTTPException(413,'File exceeds 3 MiB')
        data.extend(chunk)
    row,policy=await run_in_threadpool(service.intake,db,actor[2],meta,bytes(data))
    return service.output_source(db,row,policy)

@router.get('/documents')
def sources(matter_id:str,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    from kestrel.domain import member_and_not_walled
    def member_scope(fresh):
        if not member_and_not_walled(fresh,matter_id):raise HTTPException(403,'Matter denied')
    return protected(db,request,actor[2],matter_id,'source.list',lambda fresh:service.source_list(db,fresh,matter_id,historical),scope_check=member_scope)

@router.get('/documents/{source_id}')
def source(source_id:str,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    initial,_=service.source(db,actor[2],source_id,historical)
    def prepare(fresh):
        row,policy=service.source(db,fresh,source_id,historical)
        result=service.output_source(db,row,policy,detail=True)
        service.event(db,fresh,policy,'source.view',row.id);db.commit();return result
    return protected(db,request,actor[2],initial.matter_id,'source.view',prepare)

@router.get('/documents/{source_id}/download')
def download(source_id:str,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    initial,_=service.source(db,actor[2],source_id,historical)
    def prepare(fresh):
        row,policy=service.source(db,fresh,source_id,historical)
        service.source_integrity(row,policy);service.event(db,fresh,policy,'source.download',row.id);db.commit()
        return Response(row.data,media_type=row.media_type,headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.file_name,safe='')})
    return protected(db,request,actor[2],initial.matter_id,'source.download',prepare)

@router.get('/documents/{source_id}/reader')
def reader(source_id:str,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.adapters.document_reader import presentation
    from kestrel.services.response_guard import protected
    row,_=service.source(db,actor[2],source_id,historical)
    def prepare(fresh):
        row,policy=service.source(db,fresh,source_id,historical)
        service.source_integrity(row,policy)
        result={**service.output_source(db,row,policy),**presentation(row)}
        from kestrel.adapters.citation_anchors import anchors
        result['citation_anchors']=anchors(result['units'],source_id=row.id)
        result['can_classify_content']=fresh.org.value=='firm' and bool(fresh.roles&service.LEGAL)
        service.event(db,fresh,policy,'source.reader',row.id);db.commit()
        return result
    return protected(db,request,actor[2],row.matter_id,'source.reader',prepare)

@router.get('/documents/{source_id}/inline')
def inline_pdf(source_id:str,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected
    initial,_=service.source(db,actor[2],source_id,historical)
    def prepare(fresh):
        row,policy=service.source(db,fresh,source_id,historical);service.source_integrity(row,policy)
        if row.media_type!='application/pdf':raise HTTPException(415,'Inline original viewing is available for PDF only; use the document reader for Office/text')
        service.event(db,fresh,policy,'source.preview',row.id);db.commit()
        return Response(row.data,media_type='application/pdf',headers={'Content-Disposition':"inline; filename*=UTF-8''"+quote(row.file_name,safe=''),'Content-Security-Policy':"frame-ancestors 'self'",'X-Frame-Options':'SAMEORIGIN'})
    return protected(db,request,actor[2],initial.matter_id,'source.preview',prepare)

@router.post('/documents/{source_id}/confirm')
def confirm(source_id:str,payload:Confirm,actor=Depends(identity),db=Depends(database)):
    row,policy=service.confirm(db,actor[2],source_id,payload);return service.output_source(db,row,policy,detail=True)

@router.post('/documents/{source_id}/classification-requests',status_code=201)
def propose(source_id:str,payload:Classification,actor=Depends(identity),db=Depends(database)):
    row=service.propose_classification(db,actor[2],source_id,payload);return {'id':row.id,'state':row.state}

@router.post('/classification-requests/{request_id}/{operation}')
def classification(request_id:str,operation:Literal['approve','reject'],payload:Reason,actor=Depends(identity),db=Depends(database)):
    row=service.classification_decision(db,actor[2],request_id,operation,payload.rationale);return {'id':row.id,'state':row.state}

@router.get('/findings')
def findings(matter_id:str,request:Request,historical:bool=False,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.diligence import visible_findings
    from kestrel.services.finding_tables import guarded_read
    from kestrel.api.data_tables import checked
    return checked(db,actor[2],'findings.list',lambda:guarded_read(db,actor[2],matter_id,request,lambda fresh,audited:visible_findings(db,fresh,matter_id,historical,audited=audited)))

@router.post('/findings/{finding_id}/review')
def review(finding_id:str,payload:Review,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.finding_tables import review_candidate
    from kestrel.api.data_tables import checked
    return checked(db,actor[2],'findings.candidate_review',lambda:review_candidate(db,actor[2],finding_id,payload,request))

@router.post('/releases',status_code=201)
def create_package(payload:Package,actor=Depends(identity),db=Depends(database)):
    if len({r.finding_id for r in payload.references})!=len(payload.references):raise HTTPException(422,'Duplicate finding reference')
    row,policy=service.create_package(db,actor[2],payload);return service.package_output(db,row,policy,internal=True)

@router.get('/releases')
def packages(matter_id:str,actor=Depends(identity),db=Depends(database)):
    if matter_id not in actor[2].matters-actor[2].walls:raise HTTPException(403,'Matter access denied')
    result=[];internal=actor[2].org==O.FIRM
    for row in db.scalars(select(ReleasePackage).join(Policy,ReleasePackage.policy_id==Policy.id).where(Policy.matter_id==matter_id).order_by(ReleasePackage.created_at)):
        try:
            _,policy=service.package(db,actor[2],row.id,internal);result.append(service.package_output(db,row,policy,internal))
            service.event(db,actor[2],policy,'release.view',row.id)
        except HTTPException as error:
            if error.status_code!=403:raise
    db.commit()
    return result

@router.get('/releases/{release_id}')
def package(release_id:str,actor=Depends(identity),db=Depends(database)):
    internal=actor[2].org==O.FIRM
    row,policy=service.package(db,actor[2],release_id,internal)
    service.event(db,actor[2],policy,'release.view',row.id);db.commit()
    return service.package_output(db,row,policy,internal)

@router.post('/releases/{release_id}/{operation}')
def release_decision(release_id:str,operation:Literal['approve','antitrust','revoke'],payload:Approval,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.api.data_tables import checked
    return checked(db,actor[2],'release.'+operation,lambda:service.release_decision(db,actor[2],release_id,operation,payload,request,receipt=True))
