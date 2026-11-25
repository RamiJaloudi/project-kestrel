"""Retained email staging inherits current original-source access and no grants."""
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.services import workflow as w,data_tables as tables
from kestrel.adapters.email_source import message
from kestrel.services.auth import audit

def prepare(db,actor,sid,download=False,historical=False):
    source,policy=w.source(db,actor,sid,historical=historical);w.source_integrity(source,policy)
    if not source.file_name.lower().endswith('.eml'):raise HTTPException(422,'Email source required')
    if download:w.require_policy(db,actor,policy,'download')
    try:units,attachments=message(source.data)
    except Exception:raise HTTPException(422,'Retained email staging could not be safely verified')
    import json
    retained=[u['attachment'] for u in json.loads(source.units_json) if u.get('attachment')]
    current=[{k:v for k,v in item.items() if k!='data'} for item in attachments]
    if retained!=current:raise HTTPException(409,'Retained email attachment manifest changed')
    return source,policy,attachments

def execute(db,actor,request,sid,index=None,historical=False):
    matter=db.scalar(select(m.SourceVersion.matter_id).where(m.SourceVersion.id==sid))
    if not matter:raise HTTPException(404,'Source unavailable')
    tables.throttle(actor);before,actor=tables.begin(db,request,matter)
    source,policy,attachments=prepare(db,actor,sid,index is not None,historical);snapshot=w.snapshot(db,policy)
    if index is None:
        from kestrel.services.policy import evaluate
        from kestrel.services.auth import clock
        value={'source_id':source.id,'state':'staged_not_ingested','can_download':evaluate(db,actor,policy,'download',clock())['allowed'],'attachments':[{k:v for k,v in item.items() if k!='data'} for item in attachments]}
    else:
        value=next((a for a in attachments if a['index']==index),None)
        if not value:raise HTTPException(404,'Staged attachment unavailable')
    actor=tables.finish(db,request,matter,before);db.expire_all()
    _,current,_=prepare(db,actor,sid,index is not None,historical)
    if w.snapshot(db,current)!=snapshot:raise HTTPException(409,'Email source attributes changed while preparing staged content')
    w.event(db,actor,current,'source.attachment.download' if index is not None else 'source.attachment.staging_list',sid)
    db.commit();return value
