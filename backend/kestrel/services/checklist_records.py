"""Normalized projections and source-bound operational request logs; no legal conclusions."""
import json
from datetime import date
from sqlalchemy import select
from fastapi import HTTPException
from kestrel import models as m
from kestrel.services import checklists as c,workflow as w,review_work as rw,diligence
from kestrel.services.auth import clock,audit
from kestrel.repositories.identity import clean_scope
from kestrel.repositories import checklists as repo
from kestrel.migration_support.checklist_projection_v1 import stable,project_version,project_coverage
from kestrel.adapters.extraction import canonical,digest


def normalized(db,version,item):
    row=db.get(m.ChecklistItemRecord,stable('item:'+version.id+':'+item['item_id']))
    if row is None:raise HTTPException(409,'Checklist projection unavailable; run the additive migration')
    return row


def coverage_authority(db,actor,version,event):
    w.legal(actor,version.matter_id)
    for p in json.loads(event.source_snapshots_json).get('_restrictions',[]):
        if p['matter_id']!=version.matter_id or (p['classification']=='clean_team' and not clean_scope(db,actor.id,p['matter_id'],p['clean_team_scope'] or '',clock())):raise HTTPException(403,'Retained coverage restriction denies access')
    for sid in json.loads(event.source_ids_json):
        src,policy=w.source(db,actor,sid,historical=True)
        if src.matter_id!=version.matter_id:raise HTTPException(403,'Coverage outside matter')
        w.source_integrity(src,policy)
    for fid in json.loads(event.finding_ids_json):diligence.resolve(db,actor,fid,historical=True)


def request_output(db,actor,event):
    w.legal(actor,event.matter_id)
    evidence=list(db.scalars(select(m.ChecklistRequestEvidence).where(m.ChecklistRequestEvidence.request_event_id==event.id)))
    if not evidence and actor.id!=event.actor_id:raise HTTPException(403,'Unlinked notes are author-only')
    for record in evidence:rw.retained(db,actor,record)
    return {**{k:getattr(event,k) for k in ['id','revision','operation','actor_id','due_date','wave','workstream','jurisdiction','notes','request_reference','disclosure_reference','import_row_id','created_at']},
        'source_ids':[r.source_id for r in evidence],'author_only':not evidence}


def history(db,actor,vid,item_code):
    version=c.coverage_version(db,actor,vid);item=c.item_of(version,item_code);norm=normalized(db,version,item);records=[];requests=[]
    for row in db.scalars(select(m.ChecklistCoverageDecision).where(m.ChecklistCoverageDecision.version_id==vid,m.ChecklistCoverageDecision.item_id==item_code).order_by(m.ChecklistCoverageDecision.revision).limit(501)):
        try:
            coverage_authority(db,actor,version,row)
            records.append({'id':row.id,'revision':row.revision,'recorded_status':row.status,'kind':row.kind,'actor_id':row.actor_id,'rationale':row.rationale,
                'missing_information':row.missing_information,'created_at':row.created_at,'source_ids':json.loads(row.source_ids_json),'finding_ids':json.loads(row.finding_ids_json)})
        except HTTPException as e:
            if e.status_code not in {403,404}:raise
    for row in db.scalars(select(m.ChecklistRequestEvent).where(m.ChecklistRequestEvent.item_id==norm.id).order_by(m.ChecklistRequestEvent.revision).limit(501)):
        try:requests.append(request_output(db,actor,row))
        except HTTPException as e:
            if e.status_code!=403:raise
    if len(records)>500 or len(requests)>500:raise HTTPException(413,'Narrow the local history query')
    audit(db,'checklist.history.view','allowed',actor.id,category='legal_sme',matter_id=version.matter_id,object_id=version.id);db.commit()
    return {'version_id':vid,'item_id':item_code,'normalized_item_id':norm.id,'coverage':records,'requests':requests,'notice':c.NOTICE+' Historical status is recorded status, not a new legal conclusion. Unlinked notes are author-only.'}


def request_log(db,actor,vid,item_code,p):
    version=c.coverage_version(db,actor,vid,write=True);item=c.item_of(version,item_code);norm=normalized(db,version,item)
    h=digest(canonical({'version':vid,'item':item_code,'payload':p.model_dump()}).encode())
    old=db.scalar(select(m.ChecklistRequestEvent).where(m.ChecklistRequestEvent.actor_id==actor.id,m.ChecklistRequestEvent.request_key==p.request_key))
    if old:
        if old.input_hash!=h:raise HTTPException(409,'Request key reused with changed content')
        return request_output(db,actor,old)
    prior=db.scalar(select(m.ChecklistRequestEvent).where(m.ChecklistRequestEvent.item_id==norm.id).order_by(m.ChecklistRequestEvent.revision.desc()))
    if p.expected_revision!=(prior.revision if prior else 0):raise HTTPException(409,'Request log changed; refresh')
    if p.due_date:
        try:
            if date.fromisoformat(p.due_date).isoformat()!=p.due_date:raise ValueError()
        except ValueError:raise HTTPException(422,'ISO due date required')
    evidence=[]
    for sid in p.source_ids:
        src,policy=rw.source(db,actor,sid)
        if src.matter_id!=version.matter_id:raise HTTPException(403,'Request evidence outside matter')
        evidence.append((src,policy))
    if p.import_row_id:
        from kestrel.services.vdr_imports import get_batch
        imported=db.get(m.VdrImportRow,p.import_row_id)
        if imported is None:raise HTTPException(404,'Imported reference unavailable')
        batch=db.get(m.VdrImportBatch,imported.batch_id);get_batch(db,actor,batch.id)
        if batch.matter_id!=version.matter_id:raise HTTPException(403,'Imported reference outside matter')
        linked=set(db.scalars(select(m.DocumentSource.source_id).where(m.DocumentSource.import_row_id==imported.id)))
        if not p.source_ids or not set(p.source_ids)<=linked:raise HTTPException(422,'Link actual source versions from this imported row')
        mapped=json.loads(imported.mapped_json)
        if p.request_reference!=mapped.get('request_ref','') or p.disclosure_reference!=mapped.get('disclosure_ref',''):raise HTTPException(409,'Preserve exact imported request/disclosure references')
    row=m.ChecklistRequestEvent(matter_id=version.matter_id,item_id=norm.id,revision=(prior.revision if prior else 0)+1,operation=p.operation,actor_id=actor.id,
        due_date=p.due_date,wave=p.wave,workstream=p.workstream,jurisdiction=p.jurisdiction,notes=p.notes,request_reference=p.request_reference,
        disclosure_reference=p.disclosure_reference,import_row_id=p.import_row_id,request_key=p.request_key,input_hash=h,created_at=clock())
    db.add(row);db.flush()
    for src,policy in evidence:db.add(m.ChecklistRequestEvidence(**rw.capture(src,policy),request_event_id=row.id))
    db.flush()
    scopes={policy.clean_team_scope for _,policy in evidence if policy.classification=='clean_team'}
    for scope in sorted(scopes) if scopes else [None]:audit(db,'checklist.request.'+p.operation,'allowed',actor.id,category='clean_team' if scopes else 'legal_sme',matter_id=version.matter_id,object_id=row.id,clean_team_scope=scope)
    value=request_output(db,actor,row);db.commit();return value


def snapshot_report(db,actor,report,refs,previous=None):
    if previous:
        for old in db.scalars(select(m.ReportChecklistSnapshot).where(m.ReportChecklistSnapshot.report_id==previous.id)):
            db.add(m.ReportChecklistSnapshot(matter_id=old.matter_id,report_id=report.id,coverage_event_id=old.coverage_event_id))
        return
    sources=set();matters=set()
    for ref in refs:
        finding,policy=diligence.resolve(db,actor,ref['finding_id'])
        if finding.id!=ref['revision_id']:raise HTTPException(409,'Report finding revision changed')
        sources.add(finding.source_id);matters.add(policy.matter_id)
    versions=list(db.scalars(select(m.ChecklistVersion).where(m.ChecklistVersion.matter_id.in_(matters))))
    for version in versions:
        if version.matter_id not in actor.matters-actor.walls or c.output(db,version)['state']!='published':continue
        for item in json.loads(version.definition_json)['items']:
            event=repo.coverage(db,version.id,item['item_id'])
            if not event or not sources.intersection(json.loads(event.source_ids_json)):continue
            coverage_authority(db,actor,version,event)
            db.add(m.ReportChecklistSnapshot(matter_id=version.matter_id,report_id=report.id,coverage_event_id=event.id))


def report_coverage(db,actor,report_id):
    rw.internal(actor)
    from kestrel.services import reports
    report,release,policy=reports.read(db,actor,report_id);w.legal(actor,policy.matter_id);rows=[]
    for snapshot in db.scalars(select(m.ReportChecklistSnapshot).where(m.ReportChecklistSnapshot.report_id==report_id)):
        event=db.get(m.ChecklistCoverageDecision,snapshot.coverage_event_id);version=c.version(db,actor,event.version_id);coverage_authority(db,actor,version,event)
        rows.append({'coverage_event_id':event.id,'checklist_version_id':version.id,'checklist_hash':version.content_hash,'item_id':event.item_id,'revision':event.revision,
            'recorded_status':event.status,'created_at':event.created_at})
    w.event(db,actor,policy,'report.coverage.view',report.id);db.commit()
    return {'report_id':report_id,'snapshots':rows,'notice':'Internal exact coverage references captured when this report was generated. No snapshots on a legacy report does not mean complete or missing diligence. These records are not externally released report text.'}
