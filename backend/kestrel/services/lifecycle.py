"""Explicit local signing/closing decisions. No automatic deletion or claimed WORM storage."""
import json
from fastapi import HTTPException
from sqlalchemy import select
from kestrel import models as m
from kestrel.services import workflow as w
from kestrel.services.auth import clock,audit
from kestrel.domain import Role as R,Organization as O,member_and_not_walled
from kestrel.adapters.extraction import canonical,digest

def control_access(actor,matter):
    if actor.org==O.FIRM and R.SECURITY in actor.roles and member_and_not_walled(actor,matter):return
    w.legal(actor,matter)

def mutable(db,matter):
    state=db.scalar(select(m.MatterLifecycle).where(m.MatterLifecycle.matter_id==matter).execution_options(populate_existing=True))
    if state and state.frozen:raise HTTPException(409,'Signing snapshot frozen; content changes are closed')

def manifest(db,actor,matter,audit_ids=None,clock_as_of=None):
    w.legal(actor,matter)
    policies=list(db.scalars(select(m.DocumentPolicyVersion).where(m.DocumentPolicyVersion.matter_id==matter).order_by(m.DocumentPolicyVersion.id)))
    for policy in policies:
        # No signing manifest can bypass a wall or a clean-team partition.
        w.require_policy(db,actor,policy,'historical_read' if policy.classification_confirmed else 'triage')
    busy=db.scalar(select(m.AnalysisJob.id).where(m.AnalysisJob.matter_id==matter,m.AnalysisJob.state.in_(['queued','running'])))
    busy_ddr=db.scalar(select(m.DDRExecution.run_id).join(m.DDRRun,m.DDRRun.id==m.DDRExecution.run_id).where(m.DDRRun.matter_id==matter,m.DDRExecution.state.in_(['queued','running'])))
    busy_ocr=db.scalar(select(m.OCRJob.id).join(m.SourceVersion,m.OCRJob.source_id==m.SourceVersion.id).where(m.SourceVersion.matter_id==matter,m.OCRJob.state.in_(['queued','running'])))
    busy_ai=db.scalar(select(m.AIOperation.id).where(m.AIOperation.matter_id==matter,m.AIOperation.state=='pending'))
    busy_impact=db.scalar(select(m.ImpactPublication.id).join(m.GovernanceVersion,m.ImpactPublication.target_id==m.GovernanceVersion.id).where(m.GovernanceVersion.matter_id==matter,m.ImpactPublication.state=='pending'))
    active_clock=db.scalar(select(m.ReviewSessionLease.account_id).join(m.ReviewSession,m.ReviewSessionLease.session_id==m.ReviewSession.id).where(m.ReviewSession.matter_id==matter,m.ReviewSessionLease.lease_until>clock()))
    if busy or busy_ddr or busy_ocr or busy_ai or busy_impact or active_clock:raise HTTPException(409,'Finish or reconcile active jobs and stop reader timing before signing')
    policy_ids=[p.id for p in policies]
    sources=list(db.scalars(select(m.SourceVersion).where(m.SourceVersion.matter_id==matter).order_by(m.SourceVersion.id)))
    for source in sources:w.source_integrity(source,db.get(m.DocumentPolicyVersion,source.policy_id))
    result={'schema':'kestrel-signing-manifest-11','review_clock_as_of':clock() if clock_as_of is None else clock_as_of,'matter_id':matter,'policies':[{'id':p.id,'snapshot':w.snapshot(db,p)} for p in policies],
        'sources':[{'id':s.id,'logical_key':s.logical_key,'version':s.version_number,'file_name':s.file_name,'bytes_hash':s.bytes_hash,'text_hash':s.text_hash} for s in sources]}
    # Include all retained immutable content/decision rows; never include credentials.
    for model,column,values in [(m.SourceFinding,m.SourceFinding.policy_id,policy_ids),(m.LegalFindingRevision,m.LegalFindingRevision.policy_id,policy_ids),(m.ReleasePackage,m.ReleasePackage.policy_id,policy_ids),(m.DocumentReviewVersion,m.DocumentReviewVersion.source_id,[s.id for s in sources]),(m.GovernanceVersion,m.GovernanceVersion.matter_id,[matter]),(m.ClientSubmission,m.ClientSubmission.matter_id,[matter]),(m.ChecklistVersion,m.ChecklistVersion.matter_id,[matter])]:
        statement=select(model).where(column.in_(values))
        if model is m.GovernanceVersion:statement=statement.where(m.GovernanceVersion.kind=='legal_playbook')
        rows=list(db.scalars(statement.order_by(model.id)))
        result[model.__tablename__]=[{'id':row.id,'hash':digest(canonical({c.name:getattr(row,c.name) for c in model.__table__.columns if c.name not in {'data','parsed_json'}}).encode())} for row in rows]
    # New projection/staging records join future signing manifests; historical
    # signed manifests remain immutable and are never rewritten during backfill.
    for model in [m.FinancialFactContext,m.FinancialContextEvidence,m.FinancialContextDecision,m.FinancialExtractionCandidate,m.AgentProfile,m.AgentProfileVersion,m.AgentProfileEvent,m.AgentProfileReplacement,m.AgentProfileImpact,m.AgentProfileImpactItem,m.AgentProfileImpactTask,m.AgentProfileImpactDecision,m.AgentProfileImpactNotification,m.DDRRun,m.DDREvidence,m.DDRArtifact,m.DDRAttempt,m.DDRNodeResult,m.DDRTask,m.DDRDecision,m.DDREvent,m.DDRReportLink,m.IntelligenceProfile,m.IntelligenceProfileDecision,m.IntelligenceOverride,m.IntelligenceOverrideDecision,m.IntelligenceAlert,m.IntelligenceAlertRecipient,m.IntelligenceAlertDisposition,m.TableView,m.TableViewVersion,m.TableViewEvidence,m.TableViewShare,m.TableViewShareRecipient,m.TableViewShareDecision,m.LogicalDocument,m.DocumentVersionLink,m.VdrMappingProfile,m.VdrImportBatch,m.DocumentSource,
                  m.RecordCustodian,m.DocumentCustodian,m.CustodianLinkRetirement,m.DocumentParty,m.ReviewTask,m.ReviewTaskEvent,m.ReviewTaskNotification,
                  m.SlaCalendarVersion,m.ReviewSlaVersion,m.ReviewSlaDecision,m.ReviewSlaBinding,m.ReviewSession,m.ReviewSessionReceipt,m.ChecklistSectionRecord,m.ChecklistItemRecord,m.ChecklistCoverageProjection,m.DocumentChecklistLink,m.ChecklistFindingLink,m.ChecklistRequestEvent,m.ChecklistRequestEvidence,m.ReportChecklistSnapshot,m.ContentLabelAssertion,m.ContentLabelDecision,m.ContentLabelImpact,m.ContentImpactTask,m.SourceEmbedding,m.FinancialFact,m.FinancialFactDecision,m.FinancialAccessGate,m.FinancialReconciliation,m.FinancialResolution,m.DisclosurePlan,m.DisclosurePlanReview,m.DisclosureArtifact,m.DisclosureValidation,m.DisclosureDecision,m.ReviewSlaEscalationPlan,m.ReviewSlaPlanRecipient,m.ReviewSlaPlanDecision,m.ReviewSlaAlert,m.ReviewSlaAlertRecipient,m.ReviewSlaAlertDisposition]:
        hashes=[]
        for row in db.scalars(select(model).where(model.matter_id==matter)):
            if model in {m.FinancialFactContext,m.FinancialContextEvidence,m.FinancialContextDecision,m.FinancialExtractionCandidate}:
                from kestrel.services.financial_context import audit_records as context_records
                from kestrel.services.review_work import retained
                for record in context_records(db,row.id):retained(db,actor,record)
            if model in {m.FinancialReconciliation,m.FinancialResolution}:
                from kestrel.services import financial
                case=row if model is m.FinancialReconciliation else db.get(m.FinancialReconciliation,row.reconciliation_id)
                for fid in [case.left_id,case.right_id]:financial.read(db,actor,db.get(m.FinancialFact,fid))
            if model in {m.AgentProfileImpact,m.AgentProfileImpactTask,m.AgentProfileImpactDecision,m.AgentProfileImpactNotification}:
                from kestrel.services.agent_registry import audit_records as agent_records
                from kestrel.services.review_work import retained
                for record in agent_records(db,row.id):retained(db,actor,record)
            if model in {m.DDRRun,m.DDRArtifact,m.DDRAttempt,m.DDRNodeResult,m.DDRTask,m.DDRDecision,m.DDREvent,m.DDRReportLink}:
                from kestrel.services.ddr_runs import audit_records as graph_records
                from kestrel.services.review_work import retained
                for record in graph_records(db,row.id):retained(db,actor,record)
            if model in {m.TableView,m.TableViewVersion,m.TableViewShare,m.TableViewShareRecipient,m.TableViewShareDecision}:
                from kestrel.services.table_views import audit_records
                from kestrel.services.review_work import retained
                for record in audit_records(db,row.id):retained(db,actor,record)
            if hasattr(row,'retained_classification'):
                from kestrel.services.review_work import retained
                retained(db,actor,row)
            content={c.name:(str(getattr(row,c.name)) if c.name=='amount' else getattr(row,c.name)) for c in model.__table__.columns if c.name not in {'data','read_at','acknowledged_at'}}
            hashes.append({'hash':digest(canonical(content).encode())})
        result[model.__tablename__]=sorted(hashes,key=canonical)
    batches=list(db.scalars(select(m.VdrImportBatch.id).where(m.VdrImportBatch.matter_id==matter)))
    result['vdr_import_rows']=sorted([{'hash':digest(canonical({c.name:getattr(row,c.name) for c in m.VdrImportRow.__table__.columns}).encode())} for row in db.scalars(select(m.VdrImportRow).where(m.VdrImportRow.batch_id.in_(batches)))],key=canonical)
    releases=[row['id'] for row in result['release_packages']]
    for model,column in [(m.ReportVersion,m.ReportVersion.release_id),(m.CollaborationMessage,m.CollaborationMessage.release_id),(m.ReleaseApproval,m.ReleaseApproval.release_id)]:
        result[model.__tablename__]=[{'id':row.id,'hash':digest(canonical({c.name:getattr(row,c.name) for c in model.__table__.columns}).encode())} for row in db.scalars(select(model).where(column.in_(releases)).order_by(model.id))]
    related=[
        (m.ChecklistVersionDecision,m.ChecklistVersionDecision.version_id,[r['id'] for r in result['checklist_versions']]),
        (m.ChecklistCoverageDecision,m.ChecklistCoverageDecision.version_id,[r['id'] for r in result['checklist_versions']]),
        (m.FindingReview,m.FindingReview.finding_id,[r['id'] for r in result['source_findings']]),
        (m.OCRVerification,m.OCRVerification.source_id,[s.id for s in sources]),
        (m.SubmissionAcceptance,m.SubmissionAcceptance.submission_id,[r['id'] for r in result['client_submissions']]),
        (m.CollaborationApproval,m.CollaborationApproval.message_id,[r['id'] for r in result['collaboration_messages']]),
        (m.AnalysisJob,m.AnalysisJob.matter_id,[matter]),
        (m.OCRJob,m.OCRJob.source_id,[s.id for s in sources]),
        (m.AIOperation,m.AIOperation.matter_id,[matter]),
        (m.QuestionAnswer,m.QuestionAnswer.matter_id,[matter])]
    for model,column,values in related:
        hashes=[]
        for row in db.scalars(select(model).where(column.in_(values))):
            content={c.name:(str(getattr(row,c.name)) if c.name=='amount' else getattr(row,c.name)) for c in model.__table__.columns if c.name not in {'data','read_at','acknowledged_at'}}
            identity={c.name:getattr(row,c.name) for c in model.__table__.primary_key.columns}
            hashes.append({'key':identity,'hash':digest(canonical(content).encode())})
        result[model.__tablename__]=sorted(hashes,key=canonical)
    impacts=list(db.scalars(select(m.ImpactSnapshot.id).where(m.ImpactSnapshot.matter_id==matter)))
    tasks=list(db.scalars(select(m.GovernanceTask.id).where(m.GovernanceTask.impact_id.in_(impacts))))
    comparisons=list(db.scalars(select(m.FindingReconciliation.id).where(m.FindingReconciliation.task_id.in_(tasks))))
    for model,column,values in [(m.ImpactSnapshot,m.ImpactSnapshot.id,impacts),(m.GovernanceTask,m.GovernanceTask.id,tasks),(m.ImpactDecision,m.ImpactDecision.task_id,tasks),(m.FindingReconciliation,m.FindingReconciliation.task_id,tasks),(m.ReconciliationDecision,m.ReconciliationDecision.comparison_id,comparisons),(m.TaskClosure,m.TaskClosure.task_id,tasks)]:
        result[model.__tablename__]=[{'id':row.id,'hash':digest(canonical({c.name:getattr(row,c.name) for c in model.__table__.columns}).encode())} for row in db.scalars(select(model).where(column.in_(values)).order_by(model.id))]
    imports=list(db.scalars(select(m.TrackerImport.id).where(m.TrackerImport.matter_id==matter)))
    for model,column,values in [(m.TrackerImport,m.TrackerImport.id,imports),(m.TrackerImportApplication,m.TrackerImportApplication.import_id,imports),(m.TrackerExport,m.TrackerExport.release_id,releases),(m.PolicyRecipient,m.PolicyRecipient.policy_id,policy_ids)]:
        result[model.__tablename__]=[{'id':row.id,'hash':digest(canonical({c.name:getattr(row,c.name) for c in model.__table__.columns if c.name not in {'data','read_at','acknowledged_at'}}).encode())} for row in db.scalars(select(model).where(column.in_(values)).order_by(model.id))]
    # Bind audit history already present at proposal time. Subsequent access and
    # proposal/approval events remain append-only and do not invalidate the snapshot.
    query=select(m.AuditEvent).where(m.AuditEvent.matter_id==matter)
    if audit_ids is not None:query=query.where(m.AuditEvent.id.in_(audit_ids))
    result['audit_history']=[{'id':row.id,'hash':digest(canonical({c.name:getattr(row,c.name) for c in m.AuditEvent.__table__.columns}).encode())} for row in db.scalars(query.order_by(m.AuditEvent.id))]
    return result

def propose(db,actor,payload):
    if payload.kind in {'close','delete_client_copies'}:control_access(actor,payload.matter_id)
    else:w.legal(actor,payload.matter_id)
    state=db.get(m.MatterLifecycle,payload.matter_id)
    if payload.kind=='sign':
        if state and state.frozen:raise HTTPException(409,'Signing snapshot already frozen')
        value=manifest(db,actor,payload.matter_id)
    else:value={'schema':'kestrel-lifecycle-1','matter_id':payload.matter_id,'kind':payload.kind,'client_copies_only':payload.kind=='delete_client_copies'}
    row=m.LifecycleDecision(matter_id=payload.matter_id,kind=payload.kind,proposed_by=actor.id,payload_json=canonical(value),content_hash=digest(canonical(value).encode()),rationale=payload.rationale,created_at=clock())
    db.add(row);db.flush();audit(db,'lifecycle.propose','pending',actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id);db.commit();return output(row)

def output(row):
    return {key:getattr(row,key) for key in ['id','matter_id','kind','proposed_by','approved_by','state','content_hash','rationale','decision_rationale','created_at']}

def decide(db,actor,row,payload,decision):
    if row.kind in {'close','delete_client_copies'}:control_access(actor,row.matter_id)
    else:w.legal(actor,row.matter_id)
    if row.state!='pending' or row.proposed_by==actor.id:raise HTTPException(403,'Independent pending decision required')
    if payload.content_hash!=row.content_hash or digest(row.payload_json.encode())!=row.content_hash:raise HTTPException(409,'Exact lifecycle payload hash required')
    required=R.SECURITY if row.kind in {'close','delete_client_copies'} else R.SME
    if required not in actor.roles:raise HTTPException(403,'Scoped independent '+required.value+' required')
    db.scalar(select(m.Matter).where(m.Matter.id==row.matter_id).with_for_update())
    state=db.scalar(select(m.MatterLifecycle).where(m.MatterLifecycle.matter_id==row.matter_id).with_for_update())
    if not state:state=m.MatterLifecycle(matter_id=row.matter_id);db.add(state);db.flush()
    if decision=='approve':
        if row.kind=='sign':
            signed_payload=json.loads(row.payload_json)
            if state.frozen or digest(canonical(manifest(db,actor,row.matter_id,audit_ids=[r['id'] for r in signed_payload['audit_history']],clock_as_of=signed_payload.get('review_clock_as_of'))).encode())!=row.content_hash:raise HTTPException(409,'Matter changed; propose a fresh signing snapshot')
            state.frozen=True
        elif row.kind=='close':
            if not state.frozen:raise HTTPException(409,'Approve signing snapshot before closing external access')
            state.external_closed=True
        elif row.kind=='hold':state.legal_hold=True
        elif row.kind=='release_hold':
            if not state.legal_hold:raise HTTPException(409,'No active legal hold')
            state.legal_hold=False
        elif row.kind=='delete_client_copies':
            if not state.external_closed or state.legal_hold:raise HTTPException(409,'Close external access and resolve legal holds before client-copy deletion')
            # Retain firm SourceVersion records, all metadata and audit decisions.
            for upload in db.scalars(select(m.ClientSubmission).where(m.ClientSubmission.matter_id==row.matter_id)):
                upload.data=None;upload.parsed_json=None
        row.state='approved'
    else:row.state='rejected'
    row.approved_by=actor.id;row.decision_rationale=payload.rationale
    audit(db,'lifecycle.'+row.kind,row.state,actor.id,category='legal_sme',matter_id=row.matter_id,object_id=row.id);db.commit();return output(row)

def guard_flush(db,flush_context,instances):
    """Shared application write barrier, in addition to immutable-row DB triggers."""
    tracked={'DocumentPolicyVersion','SourceVersion','SourceFinding','LegalFindingRevision','DocumentReviewVersion','ReleasePackage','ReleaseApproval','ReportVersion','ClassificationRequest','OCRVerification','SubmissionAcceptance','CollaborationMessage','CollaborationApproval','ClientSubmission','AnalysisJob','OCRJob','GovernanceVersion'}
    tracked.update({'LogicalDocument','DocumentVersionLink','VdrMappingProfile','VdrImportBatch','VdrImportRow','DocumentSource'})
    tracked.update({'RecordCustodian','DocumentCustodian','CustodianLinkRetirement','DocumentParty','ReviewTask','ReviewTaskEvent','ReviewTaskNotification'})
    tracked.update({'SlaCalendarVersion','ReviewSlaVersion','ReviewSlaDecision','ReviewSlaBinding','ReviewSession','ReviewSessionReceipt'})
    tracked.update({'ReviewSlaAlertDisposition', 'ChecklistSectionRecord', 'DocumentChecklistLink', 'ChecklistCoverageProjection', 'ChecklistRequestEvidence', 'ChecklistVersion', 'ChecklistItemRecord', 'ChecklistCoverageDecision', 'ReportChecklistSnapshot', 'ChecklistRequestEvent', 'ReviewSlaPlanRecipient', 'ReviewSlaAlertRecipient', 'ChecklistVersionDecision', 'ReviewSlaEscalationPlan', 'ReviewSlaAlert', 'ReviewSlaPlanDecision', 'ChecklistFindingLink'})
    tracked.update({'ContentLabelAssertion','ContentLabelDecision','ContentLabelImpact'})
    tracked.update({'FinancialReconciliation','FinancialResolution','FinancialFact','FinancialFactDecision','FinancialAccessGate','SourceEmbedding','ContentImpactTask','DisclosurePlan','DisclosurePlanReview','DisclosureArtifact','DisclosureValidation','DisclosureDecision'})
    tracked.update({'FinancialFactContext','FinancialContextEvidence','FinancialContextDecision','FinancialExtractionCandidate'})
    tracked.update({'AgentProfile','AgentProfileVersion','AgentProfileEvent','AgentProfileReplacement','AgentProfileImpact','AgentProfileImpactItem','AgentProfileImpactTask','AgentProfileImpactDecision','AgentProfileImpactNotification'})
    tracked.update({'DDRRun','DDREvidence','DDRArtifact','DDRAttempt','DDRNodeResult','DDRTask','DDRDecision','DDREvent','DDRReportLink'})
    tracked.update({'IntelligenceProfile','IntelligenceProfileDecision','IntelligenceOverride','IntelligenceOverrideDecision','IntelligenceAlert','IntelligenceAlertRecipient','IntelligenceAlertDisposition'})
    tracked.update({'TableView','TableViewVersion','TableViewEvidence','TableViewShare','TableViewShareRecipient','TableViewShareDecision'})
    for row in list(db.new)+list(db.dirty)+list(db.deleted):
        name=type(row).__name__
        if name not in tracked:continue
        if name=='GovernanceVersion' and row.kind!='legal_playbook':continue
        if row in db.dirty and not db.is_modified(row,include_collections=False):continue
        matter=getattr(row,'matter_id',None)
        if name in {'ChecklistCoverageDecision','ChecklistVersionDecision'}:
            parent=db.get(m.ChecklistVersion,row.version_id);matter=parent.matter_id if parent else None
        if name=='VdrImportRow':
            parent=db.get(m.VdrImportBatch,row.batch_id);matter=parent.matter_id if parent else None
        if not matter and getattr(row,'policy_id',None):
            policy=db.get(m.DocumentPolicyVersion,row.policy_id);matter=policy.matter_id if policy else None
        for attr,model in [('source_id',m.SourceVersion),('release_id',m.ReleasePackage),('submission_id',m.ClientSubmission),('message_id',m.CollaborationMessage),('finding_id',m.SourceFinding)]:
            if matter:break
            value=getattr(row,attr,None)
            if value:
                parent=db.get(model,value)
                if parent:
                    matter=getattr(parent,'matter_id',None)
                    if not matter and getattr(parent,'policy_id',None):matter=db.get(m.DocumentPolicyVersion,parent.policy_id).matter_id
                    if not matter and isinstance(parent,m.CollaborationMessage):matter=db.get(m.DocumentPolicyVersion,db.get(m.ReleasePackage,parent.release_id).policy_id).matter_id
        if matter:
            db.scalar(select(m.Matter).where(m.Matter.id==matter).with_for_update())
            state=db.scalar(select(m.MatterLifecycle).where(m.MatterLifecycle.matter_id==matter).execution_options(populate_existing=True))
            if state and state.frozen:
                if name in {'DisclosureDecision','FinancialFactDecision','FinancialContextDecision','TableViewShareDecision','IntelligenceProfileDecision','IntelligenceOverrideDecision','DDRDecision','AgentProfileImpactDecision'} and row.operation=='revoke' and row in db.new:continue
                if name=='AgentProfileEvent' and row.operation=='archive' and row in db.new:continue
                if name=='AgentProfileImpactNotification' and row in db.dirty:
                    from sqlalchemy import inspect
                    if not any(inspect(row).attrs[c.name].history.has_changes() for c in type(row).__table__.columns if c.name not in {'read_at','acknowledged_at'}):continue
                if name=='DDREvent' and row.kind=='internal_revoke' and row in db.new:continue
                if name=='FinancialAccessGate' and not row.enabled and row in db.new:continue
                if name=='ClientSubmission' and row not in db.new and row.data is None and row.parsed_json is None and state.external_closed and not state.legal_hold:continue
                raise HTTPException(409,'Signing snapshot frozen; content changes are closed')
