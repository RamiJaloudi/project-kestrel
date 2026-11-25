from types import SimpleNamespace
from fastapi import HTTPException
from sqlalchemy import select,func
from sqlalchemy.exc import IntegrityError
from kestrel.models import OCRJob,OCRVerification,SourceVersion,Account
from kestrel.services import workflow as w
from kestrel.repositories.identity import principal
from kestrel.services.auth import clock
from kestrel.diagnostics import activity,emit
from kestrel.adapters import ocr

def authority(db,actor,source_id):
    row,policy=w.source(db,actor,source_id);w.legal(actor,row.matter_id)
    w.source_integrity(row,policy);w.require_policy(db,actor,policy,'analyze');w.processing_allowed(db,policy)
    if policy.signing_frozen or policy.superseded or row.media_type!='application/pdf':raise HTTPException(409,'Current unfrozen PDF source required')
    return row,policy
def enqueue(db,actor,source_id):
    row,policy=authority(db,actor,source_id)
    if row.extractor_version.startswith('ocr:') or row.extraction_status=='ready':raise HTTPException(409,'Source does not require OCR')
    if not ocr.available():raise HTTPException(503,'Offline OCR language models are unavailable')
    old=db.scalar(select(OCRJob).where(OCRJob.source_id==source_id))
    if old:return old
    if db.scalar(select(func.count()).select_from(OCRJob).where(OCRJob.requested_by==actor.id,OCRJob.state.in_(['queued','running'])))>=10:raise HTTPException(429,'Outstanding OCR job limit reached')
    job=OCRJob(source_id=row.id,requested_by=actor.id,created_at=clock());db.add(job)
    try:db.flush();w.event(db,actor,policy,'ocr.enqueue',job.id);db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'OCR already requested; refresh')
    return job
def verified(db,row):
    if not row.extractor_version.startswith('ocr:'):return True
    record=db.get(OCRVerification,row.id)
    return bool(record and record.text_hash==row.text_hash)
def verify(db,actor,source_id,payload):
    row,policy=w.source(db,actor,source_id,lock=True);w.legal(actor,row.matter_id);w.source_integrity(row,policy)
    if not row.extractor_version.startswith('ocr:') or policy.superseded or policy.signing_frozen:raise HTTPException(409,'Current OCR transcript required')
    if payload.text_hash!=row.text_hash:raise HTTPException(409,'OCR transcript changed; refresh')
    if db.get(OCRVerification,row.id):raise HTTPException(409,'OCR verification already recorded')
    db.add(OCRVerification(source_id=row.id,actor_id=actor.id,text_hash=row.text_hash,rationale=payload.rationale,created_at=clock()))
    w.event(db,actor,policy,'ocr.verify',row.id);db.commit()
def run_once(sessions,heartbeat=None):
    with sessions() as db:
        stmt=select(OCRJob).where(OCRJob.state=='queued').order_by(OCRJob.created_at).limit(1)
        if db.bind.dialect.name=='postgresql':stmt=stmt.with_for_update(skip_locked=True)
        job=db.scalar(stmt)
        if not job:return False
        job.state='running';job.lease_until=clock()+600;job_id=job.id;db.commit()
    activity('worker','ocr.started')
    try:
        with sessions() as db:
            job=db.get(OCRJob,job_id);account=db.get(Account,job.requested_by)
            if not account or not account.active:raise HTTPException(403,'Requester inactive')
            source,policy=authority(db,principal(db,account,clock()),job.source_id);data=source.data
        parsed=ocr.extract_pdf(data,heartbeat=heartbeat)
        with sessions() as db:
            job=db.scalar(select(OCRJob).where(OCRJob.id==job_id).with_for_update());account=db.get(Account,job.requested_by)
            if job.state!='running' or job.lease_until<clock() or not account.active:raise HTTPException(409,'OCR lease or authority changed')
            actor=principal(db,account,clock());old,policy=authority(db,actor,job.source_id)
            meta=SimpleNamespace(matter_id=old.matter_id,file_name=old.file_name,logical_key=old.logical_key,classification=policy.classification,resource_type=policy.resource_type,clean_team_scope=policy.clean_team_scope,language=old.language,governing_law=old.governing_law,wave=old.wave,previous_id=old.id)
            fresh,_=w.intake(db,actor,meta,data,parsed=parsed,commit=False)
            job.state='succeeded';job.result_source_id=fresh.id;job.lease_until=None;w.event(db,actor,policy,'ocr.complete',job.id);db.commit()
        activity('worker','ocr.completed')
    except Exception as error:
        emit('ocr.failed',component='worker',exception=error)
        with sessions() as db:
            job=db.get(OCRJob,job_id);job.state='failed';job.error_code='ocr_failed_or_denied';job.lease_until=None;db.commit()
        activity('worker','ocr.failed',failed=True)
    return True
