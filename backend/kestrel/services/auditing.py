"""Scoped audit reads and portable exports. Never export technical raw log files."""
import csv
import hashlib
import html
import io
import json
from sqlalchemy import select, or_, and_
from fastapi import HTTPException
from kestrel.models import AuditEvent, CleanTeamMembership
from kestrel.domain import Role as R, Organization as O
from kestrel.services.auth import clock
from kestrel.services.documents import load,lineage
from kestrel.repositories.identity import clean_scope

CATEGORIES={'administrative','legal_sme','clean_team','access'}
FIELDS=['id','occurred_at','actor_id','category','matter_id','object_id','clean_team_scope','action','outcome','correlation_id']


def selected(db,actor,category,matter=None,limit=1000,*,from_time=None,to_time=None):
    if category not in CATEGORIES: raise HTTPException(422,'Unknown audit category')
    if matter and (matter not in actor.matters or matter in actor.walls): raise HTTPException(403,'Matter audit denied')
    if from_time is not None and to_time is not None and from_time>to_time:raise HTTPException(422,'From time must precede to time')
    allowed_matters=actor.matters-actor.walls
    query=select(AuditEvent).where(AuditEvent.category==category)
    query=query.where(or_(AuditEvent.matter_id.is_(None),AuditEvent.matter_id.in_(allowed_matters)))
    if matter:query=query.where(AuditEvent.matter_id==matter)
    if from_time is not None:query=query.where(AuditEvent.occurred_at>=from_time)
    if to_time is not None:query=query.where(AuditEvent.occurred_at<=to_time)
    if category=='clean_team':
        memberships=db.scalars(select(CleanTeamMembership).where(CleanTeamMembership.account_id==actor.id,
            CleanTeamMembership.starts_at<=clock(),CleanTeamMembership.expires_at>clock(),CleanTeamMembership.revoked.is_(False)))
        predicates=[and_(AuditEvent.matter_id==m.matter_id,AuditEvent.clean_team_scope==m.scope) for m in memberships if m.matter_id in allowed_matters]
        if not predicates: raise HTTPException(403,'Active named clean-team scope required')
        query=query.where(or_(*predicates))
        if not (actor.org==O.FIRM and actor.roles & {R.CLEAN_AUDITOR,R.ANTITRUST}):
            query=query.where(AuditEvent.actor_id==actor.id)
    elif category=='administrative':
        if actor.org!=O.FIRM or R.ROOT_ADMIN not in actor.roles:query=query.where(AuditEvent.actor_id==actor.id)
    else:
        # Matter-wide audit requires a separate grant; SME title alone is insufficient.
        if not (actor.org==O.FIRM and R.AUDITOR in actor.roles):query=query.where(AuditEvent.actor_id==actor.id)
        else:query=query.where(or_(AuditEvent.matter_id.is_not(None),AuditEvent.actor_id==actor.id))
    rows=db.scalars(query.order_by(AuditEvent.occurred_at,AuditEvent.id).execution_options(yield_per=200))
    permitted=[]
    for row in rows:
        if row.object_id and row.action.startswith(('ddr.','agent_profile.','table_view.','intelligence.','financial_context.')):
            from kestrel.services.review_work import audit_records,retained
            try:
                for record in audit_records(db,row.object_id):retained(db,actor,record)
            except HTTPException:continue
        if row.category=='clean_team' and row.object_id:
            doc=load(db,row.object_id)
            from kestrel.services.review_work import audit_records
            work_records=audit_records(db,row.object_id)
            if work_records:
                from kestrel.services.review_work import retained
                try:
                    for record in work_records:retained(db,actor,record)
                except HTTPException:continue
                if any(r.matter_id not in allowed_matters or (r.retained_classification=='clean_team' and not clean_scope(db,actor.id,r.matter_id,r.retained_scope or '',clock())) for r in work_records):continue
                from kestrel.models import SourceVersion
                work_source=db.get(SourceVersion,work_records[0].source_id)
                if not work_source:continue
                doc=load(db,work_source.policy_id)
            checklist_docs=None
            from kestrel import models as checklist_models
            checklist= db.get(checklist_models.ChecklistCoverageDecision,row.object_id)
            if checklist:
                restrictions=json.loads(checklist.source_snapshots_json).get('_restrictions',[])
                if any(p['matter_id'] not in allowed_matters or (p['classification']=='clean_team' and not clean_scope(db,actor.id,p['matter_id'],p['clean_team_scope'] or '',clock())) for p in restrictions):continue
                checklist_docs=[]
                for source_id in json.loads(checklist.source_ids_json):
                    source=db.get(checklist_models.SourceVersion,source_id)
                    policy=load(db,source.policy_id) if source else None
                    if policy is None:checklist_docs=[];break
                    checklist_docs.append(policy)
                if not checklist_docs:continue
            if doc is None and checklist_docs is None:
                from kestrel import models as m
                for model in [m.SourceVersion,m.SourceFinding,m.LegalFindingRevision,m.ReleasePackage,m.ClientSubmission]:
                    item=db.get(model,row.object_id)
                    if item:doc=load(db,item.policy_id);break
                if doc is None:
                    for model in [m.AnalysisJob,m.OCRJob,m.SourceAccessGrant]:
                        item=db.get(model,row.object_id)
                        source_id=getattr(item,'source_id',None) or getattr(item,'document_version_id',None)
                        if source_id:
                            source=db.get(m.SourceVersion,source_id)
                            if source:doc=load(db,source.policy_id);break
                if doc is None:
                    for model in [m.ReportVersion,m.CollaborationMessage]:
                        item=db.get(model,row.object_id)
                        if item:
                            package=db.get(m.ReleasePackage,item.release_id)
                            if package:doc=load(db,package.policy_id);break
                if doc is None:continue
            try: sources=[p for d in checklist_docs for p in lineage(db,d)] if checklist_docs is not None else lineage(db,doc)
            except ValueError:continue
            from kestrel.services.content_labels import guard as content_guard
            if any(content_guard(db,actor,s,'historical_read',clock()) for s in sources):continue
            if any(s.matter_id not in allowed_matters or
                   (s.classification=='clean_team' and (not s.clean_team_scope or not clean_scope(db,actor.id,s.matter_id,s.clean_team_scope,clock()))) for s in sources):continue
        permitted.append({f:getattr(row,f) for f in FIELDS})
        if len(permitted)>limit:raise HTTPException(413,'Narrow the audit filter; permitted export limit exceeded')
    return permitted


def render(rows,format,actor,filters):
    if format=='jsonl':
        data=''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows)
        media='application/x-ndjson'
    elif format=='csv':
        stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=FIELDS);writer.writeheader()
        # Formula injection defenses also apply to administrative action labels.
        writer.writerows({k:("'"+v if isinstance(v,str) and v[:1] in '=+-@\t\r' else v) for k,v in row.items()} for row in rows)
        data=stream.getvalue();media='text/csv'
    elif format=='html':
        data='<!doctype html><meta charset="utf-8"><title>Kestrel scoped audit report</title><h1>Scoped audit report</h1><table><tr>'+''.join('<th>'+f+'</th>' for f in FIELDS)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(row[f] or ''))+'</td>' for f in FIELDS)+'</tr>' for row in rows)+'</table>'
        media='text/html'
    elif format=='pdf':
        from kestrel.adapters.audit_pdf import render as pdf
        data=pdf(rows,actor,filters);media='application/pdf'
    else:raise HTTPException(422,'Unsupported export format')
    manifest={'schema_version':1,'exported_at':clock(),'exported_by':actor.id,'filters':filters,
              'event_ids':[row['id'] for row in rows],'count':len(rows),'format':format,
              'sha256':hashlib.sha256(data.encode() if isinstance(data,str) else data).hexdigest(),'immutable_storage':False}
    return data,media,manifest
