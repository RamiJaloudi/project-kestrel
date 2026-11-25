from typing import Literal
from fastapi import APIRouter,Depends,Request,Response,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select
from kestrel import models as m
from kestrel.api.auth import identity,database
from kestrel.services import trackers as service,workflow as w
from kestrel.services.auth import authenticate

router=APIRouter(prefix='/api/v1/trackers',tags=['Diligence trackers and Excel exchange'])
Register=Literal['coverage','risk','consent']


class Apply(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    row_numbers:list[int]=Field(min_length=1,max_length=100)
    rationale:str=Field(min_length=5,max_length=1000)
    attest_reviewed:bool=Field(strict=True)
    idempotency_key:str=Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_-]+$')


class Export(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    matter_id:str=Field(max_length=36)
    register_kind:Register=Field(alias='register')
    audience:Literal['halden','castlegate']
    recipient_upn:str=Field(min_length=1,max_length=128)
    title:str=Field(min_length=3,max_length=160)
    record_ids:list[str]=Field(min_length=1,max_length=100)
    row_edits:dict[str,dict[str,str]]=Field(default_factory=dict,max_length=100)


@router.get('/templates/{register}')
def template(register:Register,matter_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    content=service.template(db,actor[2],matter_id,register)
    db.expire_all();fresh=authenticate(db,request)[2]
    w.legal(fresh,matter_id)
    # A freshly scoped template must not outlive a revoked row permission.
    from openpyxl import load_workbook
    import io
    book=load_workbook(io.BytesIO(content),read_only=True,data_only=False)
    try:
        for row in book['Records'].iter_rows(min_row=2,values_only=True):
            if row[0]:service.current(db,fresh,matter_id,register,row[0])
    finally:book.close()
    return Response(content,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="kestrel-{register}-internal-template.xlsx"'})


@router.post('/imports',status_code=201)
async def stage(request:Request,matter_id:str,register:Register,file_name:str,synthetic:bool=False,actor=Depends(identity),db=Depends(database)):
    w.legal(actor[2],matter_id)
    if not synthetic:raise HTTPException(422,'Confirm this workbook contains only synthetic data')
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>3*1024*1024:raise HTTPException(413,'Maximum workbook size is 3 MiB')
    row=service.stage(db,actor[2],matter_id,register,file_name,bytes(data))
    result=service.preview(db,actor[2],row);db.commit();return result


@router.get('/imports/{import_id}')
def preview(import_id:str,actor=Depends(identity),db=Depends(database)):
    result=service.preview(db,actor[2],service.read_import(db,actor[2],import_id));db.commit();return result


@router.post('/imports/{import_id}/apply')
def apply(import_id:str,payload:Apply,actor=Depends(identity),db=Depends(database)):
    if not payload.attest_reviewed:raise HTTPException(422,'Explicit lawyer review attestation required')
    return service.apply(db,actor[2],import_id,payload)


@router.get('/recipients')
def recipients(matter_id:str,audience:Literal['halden','castlegate'],actor=Depends(identity),db=Depends(database)):
    return service.recipients(db,actor[2],matter_id,audience)


@router.post('/exports',status_code=201)
def create_export(payload:Export,actor=Depends(identity),db=Depends(database)):
    row=service.create_export(db,actor[2],payload)
    return service.output_export(db,actor[2],row)


@router.get('/exports')
def exports(matter_id:str,actor=Depends(identity),db=Depends(database)):
    if matter_id not in actor[2].matters-actor[2].walls:raise HTTPException(403,'Matter denied')
    result=[]
    for row in db.scalars(select(m.TrackerExport).join(m.ReleasePackage,m.TrackerExport.release_id==m.ReleasePackage.id).join(m.DocumentPolicyVersion,m.ReleasePackage.policy_id==m.DocumentPolicyVersion.id).where(m.DocumentPolicyVersion.matter_id==matter_id).order_by(m.TrackerExport.created_at.desc(),m.TrackerExport.id)):
        try:
            result.append(service.output_export(db,actor[2],row))
            _,_,policy=service.read_export(db,actor[2],row.id);w.event(db,actor[2],policy,'tracker.view',row.id)
        except HTTPException as error:
            if error.status_code!=403:raise
    db.commit();return result


@router.get('/exports/{export_id}')
def export(export_id:str,actor=Depends(identity),db=Depends(database)):
    row,_,policy=service.read_export(db,actor[2],export_id);result=service.output_export(db,actor[2],row)
    w.event(db,actor[2],policy,'tracker.view',row.id);db.commit();return result


@router.get('/exports/{export_id}/download')
def download(export_id:str,request:Request,actor=Depends(identity),db=Depends(database)):
    row,_,policy=service.read_export(db,actor[2],export_id)
    db.expire_all();fresh=authenticate(db,request)[2];row,_,policy=service.read_export(db,fresh,export_id)
    w.event(db,fresh,policy,'tracker.download',row.id);db.commit()
    suffix='-historical' if any(p.superseded for p in w.lineage(db,policy)) else '' if policy.released else '-draft'
    return Response(row.data,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="kestrel-{row.register}-{row.id[:8]}{suffix}.xlsx"','X-Content-SHA256':row.bytes_hash})
