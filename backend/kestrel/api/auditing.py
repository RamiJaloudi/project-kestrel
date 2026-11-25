from typing import Literal
from fastapi import APIRouter,Depends,Query,Response,Request,HTTPException
from pydantic import ValidationError
from kestrel.api.auth import identity,database
from kestrel.schemas.audit_tables import AuditFilters,AuditTableQuery,AuditTableExport,AuditTablePage
from kestrel.services import audit_tables

router=APIRouter(prefix='/api/v1/audit',tags=['Scoped audit reports'])


def legacy_filters(category,matter_id,from_time,to_time):
    try:return AuditFilters(category=category,matter_id=matter_id,from_time=from_time,to_time=to_time)
    except ValidationError:raise HTTPException(422,'Invalid audit scope or time window') from None


@router.get('/events')
def events(request:Request,category:Literal['administrative','legal_sme','clean_team','access'],matter_id:str|None=None,from_time:int|None=Query(default=None,ge=0),to_time:int|None=Query(default=None,ge=0),
           actor=Depends(identity),db=Depends(database)):
    return audit_tables.events(db,actor[2],request,legacy_filters(category,matter_id,from_time,to_time))


@router.post('/query',response_model=AuditTablePage)
def query(payload:AuditTableQuery,request:Request,actor=Depends(identity),db=Depends(database)):
    return audit_tables.query(db,actor[2],request,payload)


@router.post('/export-query')
def export_query(payload:AuditTableExport,request:Request,actor=Depends(identity),db=Depends(database)):
    data=audit_tables.export(db,actor[2],request,payload.audit_filters,payload.format,payload=payload)
    return Response(data,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="kestrel-audit.zip"'})


@router.get('/export')
def export(request:Request,category:Literal['administrative','legal_sme','clean_team','access'],
           format:Literal['jsonl','csv','html','pdf']='jsonl',matter_id:str|None=None,from_time:int|None=Query(default=None,ge=0),to_time:int|None=Query(default=None,ge=0),
           actor=Depends(identity),db=Depends(database)):
    data=audit_tables.export(db,actor[2],request,legacy_filters(category,matter_id,from_time,to_time),format)
    return Response(data,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="kestrel-audit.zip"'})
