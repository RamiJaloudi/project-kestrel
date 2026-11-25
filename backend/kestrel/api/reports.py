import json
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Response,Request
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel.api.auth import identity,database
from kestrel.models import ReportVersion,ReleasePackage,DocumentPolicyVersion as Policy
from kestrel.services import reports as service,workflow as w
router=APIRouter(prefix='/api/v1/reports',tags=['Report drafting and board packs'])
class Generate(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(max_length=36)
    audience:Literal['halden','castlegate']
    kind:Literal['due_diligence','board_pack']
    title:str=Field(min_length=3,max_length=160)
    finding_ids:list[str]=Field(min_length=1,max_length=30)
class Section(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    heading:str=Field(min_length=3,max_length=160)
    text:str=Field(min_length=5,max_length=2000)
class Edit(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title:str=Field(min_length=3,max_length=160)
    overview:str=Field(min_length=10,max_length=4000)
    coverage:str=Field(min_length=10,max_length=4000)
    sections:list[Section]=Field(min_length=1,max_length=30)
@router.post('/generate',status_code=201)
def generate(payload:Generate,actor=Depends(identity),db=Depends(database)):
    if len(set(payload.finding_ids))!=len(payload.finding_ids):raise HTTPException(422,'Duplicate finding')
    return service.generate(db,actor[2],payload)
@router.get('')
def listing(matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.response_guard import protected,member_check
    def prepare(fresh):
        rows=[]
        for item in db.scalars(select(ReportVersion).join(ReleasePackage,ReportVersion.release_id==ReleasePackage.id).join(Policy,ReleasePackage.policy_id==Policy.id).where(Policy.matter_id==matter_id).order_by(ReportVersion.created_at.desc())):
            try:
                row,release,policy=service.read(db,fresh,item.id);rows.append(service.output(db,row,release,policy,fresh.org.value=='firm'));w.event(db,fresh,policy,'report.view',row.id)
            except HTTPException as e:
                if e.status_code!=403:raise
        db.commit();return rows
    return protected(db,request,actor[2],matter_id,'report.list',prepare,scope_check=member_check(matter_id))

@router.post('/{report_id}/versions',status_code=201)
def edit(report_id:str,payload:Edit,actor=Depends(identity),db=Depends(database)):
    return service.revise(db,actor[2],report_id,payload)
@router.get('/{report_id}/download/{kind}')
def download(report_id:str,kind:Literal['docx','pdf','xlsx'],request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.adapters.report_export import export
    row,release,policy=service.read(db,actor[2],report_id)
    if kind=='pdf':
        from kestrel.services.ddr_runs import require_internal
        require_internal(db,release.id)
    status='Audience approved' if policy.released and not any(p.superseded for p in w.lineage(db,policy)) else 'DRAFT for legal review'
    content=export(json.loads(row.body_json),kind,status)
    from kestrel.repositories.identity import principal
    from kestrel.models import Account
    from kestrel.services.auth import clock
    from kestrel.services.auth import authenticate
    db.expire_all();fresh=authenticate(db,request)[2];service.read(db,fresh,report_id)
    if kind=='pdf':
        from kestrel.services.ddr_runs import require_internal
        require_internal(db,release.id)
    w.event(db,fresh,policy,'report.download',row.id);db.commit()
    media={'docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','pdf':'application/pdf','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
    return Response(content,media_type=media[kind],headers={'Content-Disposition':f'attachment; filename="kestrel-report-v{row.version_number}.{kind}"'})

class AIDraft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_key:str=Field(min_length=8,max_length=128,pattern=r'^[a-zA-Z0-9_-]+$')

@router.post('/{report_id}/ai-draft',status_code=201)
def ai_draft(report_id:str,payload:AIDraft,request:Request,actor=Depends(identity),db=Depends(database)):
    from kestrel.services.report_ai import draft
    return draft(db,request.app.state.sessions,request,actor[2],report_id,payload)
