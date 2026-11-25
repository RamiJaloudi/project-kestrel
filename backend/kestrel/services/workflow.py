"""Versioned synthetic source -> cited candidate -> human review -> audience release."""
import json
import re
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from kestrel.models import (SourceVersion,DocumentPolicyVersion as Policy,SourceFinding,FindingReview,
    ReleasePackage,ReleaseApproval,PolicySource,ClassificationRequest,GovernanceVersion)
from kestrel.domain import Role as R,Organization as O,member_and_not_walled
from kestrel.repositories.identity import clean_scope
from kestrel.services.auth import clock,audit
from kestrel.services.documents import snapshot,lineage
from kestrel.services.policy import require
from kestrel.adapters.extraction import extract,canonical,digest

LEGAL={R.LAWYER,R.SME,R.ANTITRUST}
SOURCE_TYPES={'contract','licence','pricing','financial','legal_advice','client_upload','tracker','report'}

def legal(actor,matter):
    if actor.org!=O.FIRM or not actor.roles&LEGAL or not member_and_not_walled(actor,matter):raise HTTPException(403,'Scoped legal access required')

def require_policy(db,actor,policy,action='read'):
    return require(db,actor,policy,action,clock())

def source(db,actor,source_id,historical=False,lock=False):
    statement=select(SourceVersion).where(SourceVersion.id==source_id)
    if lock:statement=statement.with_for_update()
    row=db.scalar(statement)
    if row is None:raise HTTPException(404,'Source version unavailable')
    policy=db.get(Policy,row.policy_id)
    action='historical_read' if historical and policy.superseded else ('read' if policy.classification_confirmed else 'triage')
    require_policy(db,actor,policy,action)
    return row,policy

def source_integrity(row,policy):
    if digest(row.data)!=row.bytes_hash or policy.source_hash!=row.bytes_hash or digest(canonical(json.loads(row.units_json)).encode())!=row.text_hash:
        raise HTTPException(409,'Source evidence integrity check failed')

def output_source(db,row,policy,detail=False):
    result={k:getattr(row,k) for k in ['id','matter_id','logical_key','version_number','previous_id','file_name','language','governing_law','wave','bytes_hash','text_hash','extraction_status','extractor_version']}
    result.update({k:getattr(policy,k) for k in ['classification','classification_confirmed','resource_type','review_state','superseded','clean_team_scope','ai_restricted']})
    result['snapshot_hash']=snapshot(db,policy)
    from kestrel.models import DocumentVersionLink
    identity=db.get(DocumentVersionLink,row.id)
    result['document_id']=identity.document_id if identity else None
    from kestrel.services.ocr_jobs import verified
    if not verified(db,row):result['extraction_status']='ocr_review'
    if detail:
        source_integrity(row,policy);result['units']=json.loads(row.units_json)
        result['classification_requests']=[{'id':r.id,'classification':r.classification,'resource_type':r.resource_type,'state':r.state,'proposed_by':r.proposed_by,'rationale':r.rationale}
            for r in db.scalars(select(ClassificationRequest).where(ClassificationRequest.source_id==row.id))]
    return result

def source_list(db,actor,matter,historical=False):
    if not member_and_not_walled(actor,matter):raise HTTPException(403,'Matter access denied')
    result=[]
    for row in db.scalars(select(SourceVersion).where(SourceVersion.matter_id==matter).order_by(SourceVersion.created_at,SourceVersion.logical_key,SourceVersion.version_number)):
        try:
            _,policy=source(db,actor,row.id,historical)
            result.append(output_source(db,row,policy))
        except HTTPException as error:
            if error.status_code!=403:raise
    return result

def intake(db,actor,meta,data,*,parsed=None,commit=True):
    legal(actor,meta.matter_id)
    from kestrel.services.lifecycle import mutable
    mutable(db,meta.matter_id)
    from kestrel.models import Matter
    db.scalar(select(Matter).where(Matter.id==meta.matter_id).with_for_update())
    # Serialize against signing, then recheck frozen state after acquiring the matter lock.
    mutable(db,meta.matter_id)
    from kestrel.services import vdr_imports
    context=vdr_imports.upload_context(db,actor,meta)
    if meta.resource_type not in SOURCE_TYPES:raise HTTPException(422,'Supported source type required')
    parsed=parsed or extract(meta.file_name,data)
    if parsed.get('sensitive_hidden') and (meta.classification!='clean_team' or not meta.clean_team_scope):raise HTTPException(422,'Hidden or opaque new-format content requires explicitly scoped clean-team handling before intake')
    if context:
        # Replayed metadata/file upload returns the exact retained version, without
        # superseding it or creating another extraction/version/analysis job.
        from kestrel.models import DocumentSource
        for linked in db.scalars(select(DocumentSource).where(DocumentSource.import_row_id==context[0].id)):
            old,policy=source(db,actor,linked.source_id,historical=True)
            if old.bytes_hash==parsed['bytes_hash']:
                source_integrity(old,policy)
                return old,policy
        current=db.scalar(select(SourceVersion).join(Policy,SourceVersion.policy_id==Policy.id).where(
            SourceVersion.matter_id==meta.matter_id,SourceVersion.logical_key==meta.logical_key,Policy.superseded==False))
        if current and current.bytes_hash==parsed['bytes_hash']:
            current,policy=source(db,actor,current.id);source_integrity(current,policy)
            from kestrel.repositories.document_identity import attach
            vdr_imports.record_source(db,actor,context,current,attach(db,current))
            db.commit() if commit else db.flush()
            return current,policy
    all_text='\n'.join(u['text'] for u in parsed['units']).casefold()
    classification=meta.classification
    resource_type=meta.resource_type
    if any(t in all_text for t in ['privileged','internal legal advice','anwaltlich vertraulich']):resource_type='legal_advice'
    if resource_type=='legal_advice' and classification=='ordinary':classification='privileged'
    if resource_type=='pricing' or any(t in all_text for t in ['clean-team','clean team','wettbewerblich sensibel']):classification='clean_team'
    scope=meta.clean_team_scope or ('pricing' if classification=='clean_team' else None)
    if classification=='clean_team' and not clean_scope(db,actor.id,meta.matter_id,scope,clock()):raise HTTPException(403,'Named clean-team intake scope required')
    previous=None
    if meta.previous_id:
        previous,old_policy=source(db,actor,meta.previous_id,lock=True)
        if previous.matter_id!=meta.matter_id or previous.logical_key!=meta.logical_key:raise HTTPException(409,'Previous version must match matter and document key')
        if old_policy.superseded or old_policy.signing_frozen:raise HTTPException(409,'Previous version is not current or is frozen')
        if old_policy.classification=='clean_team':
            classification='clean_team';scope=old_policy.clean_team_scope
            if not clean_scope(db,actor.id,meta.matter_id,scope or '',clock()):raise HTTPException(403,'Named clean-team intake scope required')
        elif old_policy.classification=='privileged' and classification=='ordinary':classification='privileged'
        if old_policy.resource_type=='legal_advice':
            resource_type='legal_advice'
            if classification=='ordinary':classification='privileged'
        old_policy.superseded=True
    elif db.scalar(select(SourceVersion.id).where(SourceVersion.matter_id==meta.matter_id,SourceVersion.logical_key==meta.logical_key)):
        raise HTTPException(409,'Document exists; select its current version to add a new version')
    policy=Policy(matter_id=meta.matter_id,document_id=meta.logical_key,source_hash=parsed['bytes_hash'],resource_type=resource_type,
        classification=classification,classification_confirmed=False,review_state='candidate',clean_team_scope=scope,
        ai_restricted=(bool(previous and old_policy.ai_restricted) or any(t in all_text for t in ['no ai processing','ai processing prohibited','keine ki-verarbeitung'])))
    db.add(policy);db.flush()
    row=SourceVersion(policy_id=policy.id,matter_id=meta.matter_id,logical_key=meta.logical_key,version_number=previous.version_number+1 if previous else 1,
        previous_id=previous.id if previous else None,file_name=meta.file_name,media_type=parsed['media_type'],data=data,
        bytes_hash=parsed['bytes_hash'],text_hash=parsed['text_hash'],units_json=canonical(parsed['units']),language=meta.language,
        governing_law=meta.governing_law,extraction_status=parsed['status'],extractor_version=parsed['extractor'],uploaded_by=actor.id,created_at=clock(),wave=meta.wave)
    db.add(row);db.flush()
    from kestrel.repositories.document_identity import attach
    doc=attach(db,row);vdr_imports.record_source(db,actor,context,row,doc)
    event(db,actor,policy,'source.ingest',row.id)
    try:db.commit() if commit else db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Concurrent document version; refresh')
    return row,policy

def event(db,actor,policy,action,object_id,outcome='allowed'):
    parents=lineage(db,policy)
    scopes={item.clean_team_scope for item in parents if item.classification=='clean_team'}
    from kestrel.services.content_labels import policy_records
    for item in parents:
        scopes.update(r['scope'] for r in policy_records(db,item.id) if r['scope'])
    for scope in sorted(s for s in scopes if s) if scopes else [None]:
        audit(db,action,outcome,actor.id,category='clean_team' if scopes else 'legal_sme',matter_id=policy.matter_id,object_id=object_id,clean_team_scope=scope)

def confirm(db,actor,source_id,payload):
    row,policy=source(db,actor,source_id,lock=True)
    require_verified_ocr(db,row)
    if policy.signing_frozen or policy.superseded:raise HTTPException(409,'Frozen or historical source cannot be confirmed')
    if snapshot(db,policy)!=payload.snapshot_hash:raise HTTPException(409,'Intake state changed; refresh')
    policy.classification_confirmed=True
    event(db,actor,policy,'classification.confirm',row.id)
    db.add(ClassificationRequest(source_id=row.id,proposed_by=actor.id,classification=policy.classification,resource_type=policy.resource_type,
        rationale=payload.rationale,snapshot_hash=payload.snapshot_hash,state='confirmed',reviewer_id=actor.id,
        decision_rationale='Intake confirmed without relaxing access',created_at=clock()))
    db.commit();return row,policy

def propose_classification(db,actor,source_id,payload):
    row,policy=source(db,actor,source_id,lock=True)
    if policy.signing_frozen or policy.superseded:raise HTTPException(409,'Current unfrozen source required')
    if snapshot(db,policy)!=payload.snapshot_hash:raise HTTPException(409,'Intake state changed; refresh')
    request=ClassificationRequest(source_id=row.id,proposed_by=actor.id,classification=payload.classification,resource_type=payload.resource_type,
        rationale=payload.rationale,snapshot_hash=payload.snapshot_hash,created_at=clock())
    db.add(request);db.flush();event(db,actor,policy,'classification.propose',request.id);db.commit();return request

def classification_decision(db,actor,request_id,operation,rationale):
    request=db.scalar(select(ClassificationRequest).where(ClassificationRequest.id==request_id).with_for_update())
    if request is None:raise HTTPException(404,'Classification request unavailable')
    row,policy=source(db,actor,request.source_id,lock=True)
    if actor.id==request.proposed_by:raise HTTPException(403,'Independent classification approver required')
    required={R.ANTITRUST} if policy.classification=='clean_team' or request.classification=='clean_team' else {R.SME}
    if policy.resource_type=='legal_advice' and request.resource_type!='legal_advice':required.add(R.SME)
    if not required<=actor.roles:raise HTTPException(403,'Scoped legal/antitrust classification approval required')
    if request.state!='pending' or policy.signing_frozen or policy.superseded:raise HTTPException(409,'Current pending request required')
    if request.snapshot_hash!=snapshot(db,policy):raise HTTPException(409,'Stale classification request')
    if operation=='approve':
        if request.classification=='clean_team' and not policy.clean_team_scope:raise HTTPException(409,'A named intake scope is required before tightening to clean team')
        policy.classification=request.classification;policy.resource_type=request.resource_type;policy.classification_confirmed=True
    request.state='approved' if operation=='approve' else 'rejected';request.reviewer_id=actor.id;request.decision_rationale=rationale
    event(db,actor,policy,'classification.'+operation,request.id);db.commit();return request

def processing_allowed(db,policy,external=False):
    # Environment approval cannot clear unreviewed retained workbook metadata.
    # Traverse the original lineage for report/finding callers as well as sources.
    from kestrel.adapters.workbook_safety import processing
    try:parents=lineage(db,policy)
    except ValueError:raise HTTPException(403,'Processing source lineage is unavailable') from None
    for parent in parents:
        workbook=db.scalar(select(SourceVersion).where(SourceVersion.policy_id==parent.id))
        if workbook:processing(workbook,parent)
    from kestrel.models import ProcessingReplacement
    retired=set(db.scalars(select(ProcessingReplacement.old_id).where(ProcessingReplacement.state=='approved')))
    policies=list(db.scalars(select(GovernanceVersion).where(GovernanceVersion.matter_id==policy.matter_id,GovernanceVersion.kind=='environment_policy',GovernanceVersion.state=='published')))
    if not policies:raise HTTPException(409,'An approved processing policy is required')
    for item in policies:
        if item.id in retired:continue
        definition=json.loads(item.definition_json)
        if definition['block_ai'] or 'OTHER' not in definition['allowed_regions'] or (external and (definition['block_cloud'] or definition['block_external'])):
            raise HTTPException(403,'Processing policy prohibits this engine/environment')

def analyze_source(row,definition):
    units=json.loads(row.units_json);results=[]
    for rule in definition['rules']:
        evidence=[]
        for unit in units:
            for trigger in rule['triggers']:
                match=re.search(re.escape(trigger),unit['text'],re.IGNORECASE)
                if match:
                    evidence.append({'unit':unit['number'],'locator':unit['locator'],'start':match.start(),'end':match.end(),'quote':unit['text'][match.start():match.end()]});break
        if evidence:results.append({'rule_id':rule['id'],'summary':rule['description'],'evidence':evidence[:20]})
    return {'findings':results,'source_hash':row.bytes_hash,'text_hash':row.text_hash,'model_config':'literal-extraction-v1','taxonomy_version':'synthetic-contract-v1'}

def save_findings(db,job,result):
    row=db.get(SourceVersion,job.document_version_id);source_policy=db.get(Policy,row.policy_id)
    source_integrity(row,source_policy)
    if result.get('source_hash')!=row.bytes_hash or result.get('text_hash')!=row.text_hash:raise HTTPException(409,'Analysis source snapshot mismatch')
    units={u['number']:u for u in json.loads(row.units_json)}
    rules={r['id'] for r in json.loads(db.get(GovernanceVersion,job.playbook_id).definition_json)['rules']}
    for finding in result['findings']:
        if finding['rule_id'] not in rules or not finding['evidence']:raise HTTPException(409,'Unsupported rule or missing evidence')
        for item in finding['evidence']:
            unit=units.get(item['unit'])
            if not unit or not 0<=item['start']<item['end']<=len(unit['text']) or unit['text'][item['start']:item['end']]!=item['quote']:
                raise HTTPException(409,'Evidence span does not match immutable source')
        content_hash=digest(canonical({'source':row.bytes_hash,'text':row.text_hash,'playbook':job.playbook_hash,'finding':finding}).encode())
        policy=Policy(matter_id=row.matter_id,document_id=row.logical_key,source_hash=content_hash,resource_type='finding',classification=source_policy.classification,
            classification_confirmed=True,review_state='candidate',clean_team_scope=source_policy.clean_team_scope,ai_restricted=source_policy.ai_restricted)
        db.add(policy);db.flush();db.add(PolicySource(artifact_id=policy.id,source_id=source_policy.id))
        db.add(SourceFinding(policy_id=policy.id,source_id=row.id,job_id=job.id,rule_id=finding['rule_id'],summary=finding['summary'][:2000],
            evidence_json=canonical(finding['evidence']),playbook_id=job.playbook_id,playbook_hash=job.playbook_hash,
            model_config=result['model_config'],taxonomy_version=result['taxonomy_version'],created_at=clock()))

def finding(db,actor,finding_id,historical=False):
    from kestrel.services.diligence import resolve
    return resolve(db,actor,finding_id,historical)

def finding_output(db,row,policy):
    from kestrel.services.diligence import output
    return output(db,row,policy)

def review_finding(db,actor,finding_id,payload,*,commit=True):
    row,policy=finding(db,actor,finding_id)
    db.refresh(policy,with_for_update=True)
    source_row,source_policy=source(db,actor,row.source_id,lock=True)
    source_integrity(source_row,source_policy)
    if policy.review_state!='candidate' or source_policy.signing_frozen:raise HTTPException(409,'Unfrozen candidate finding required')
    review=FindingReview(finding_id=row.id,reviewer_id=actor.id,decision=payload.decision,rationale=payload.rationale,created_at=clock())
    db.add(review);policy.review_state=payload.decision
    if payload.decision=='reviewed':source_policy.review_state='reviewed'
    event(db,actor,policy,'finding.'+payload.decision,row.id)
    try:db.commit() if commit else db.flush()
    except IntegrityError:db.rollback();raise HTTPException(409,'Finding already decided')
    return row,policy

def package_output(db,row,policy,internal=False):
    from kestrel.services.finding_release_guard import denial
    if denial(db,policy):
        revoked=db.scalar(select(ReleaseApproval.id).where(ReleaseApproval.release_id==row.id,ReleaseApproval.kind=='revoke'))
        if internal and not policy.released and revoked:return {'id':row.id,'revoked':True}
        raise HTTPException(403,'Release access denied: RETAINED_FINDING_LINEAGE_UNBOUND')
    result={'id':row.id,'title':row.title,'summary':row.summary,'audience':policy.audience,'released':policy.released,
        'references':json.loads(row.references_json),'content_hash':row.content_hash}
    if internal:
        from kestrel.models import ReportVersion
        result['generated_report']=db.scalar(select(ReportVersion.id).where(ReportVersion.release_id==row.id)) is not None
        result.update(created_by=row.created_by,snapshot_hash=snapshot(db,policy),antitrust_approved=policy.antitrust_approved,
            lineage_stale=any(p.superseded for p in lineage(db,policy)),
            clean_team_required=any(p.classification=='clean_team' for p in lineage(db,policy)),
            approvals=[{'kind':a.kind,'actor_id':a.actor_id,'rationale':a.rationale} for a in db.scalars(select(ReleaseApproval).where(ReleaseApproval.release_id==row.id))])
    return result

def package(db,actor,release_id,internal=False,lock=False):
    statement=select(ReleasePackage).where(ReleasePackage.id==release_id)
    if lock:statement=statement.with_for_update()
    row=db.scalar(statement)
    if row is None:raise HTTPException(404,'Release unavailable')
    policy=db.get(Policy,row.policy_id)
    if internal:legal(actor,policy.matter_id)
    from kestrel.services.finding_release_guard import denial
    if denial(db,policy):raise HTTPException(403,'Release access denied: RETAINED_FINDING_LINEAGE_UNBOUND')
    require_policy(db,actor,policy,'historical_read' if internal else 'read')
    if not internal:
        from kestrel.services.ddr_runs import require_internal
        require_internal(db,release_id)
    return row,policy

def create_package(db,actor,payload):
    legal(actor,payload.matter_id)
    policies=[];refs=[];finding_policies=[]
    for reference in payload.references:
        row,policy=finding(db,actor,reference.finding_id)
        if policy.matter_id!=payload.matter_id or policy.review_state!='reviewed':raise HTTPException(409,'Reviewed same-matter findings required')
        from kestrel.models import LegalFindingRevision
        expected=getattr(reference,'revision_id',None)
        if (isinstance(row,LegalFindingRevision) and expected!=row.id) or (expected is not None and expected!=row.id):raise HTTPException(409,'Finding revision changed; refresh and draft against the exact current version')
        refs.append({**reference.model_dump(),'revision_id':row.id});finding_policies.append(policy)
        policies.extend(lineage(db,policy))
    if payload.audience=='castlegate' and any(p.classification=='privileged' or p.resource_type=='legal_advice' for p in policies):raise HTTPException(403,'Privileged lineage cannot be released to the bank')
    if any(p.signing_frozen or p.superseded for p in policies):raise HTTPException(409,'Frozen or historical sources require a new approved workflow')
    digest_value=digest(canonical({'title':payload.title,'summary':payload.summary,'references':refs,'audience':payload.audience}).encode())
    policy=Policy(matter_id=payload.matter_id,document_id='audience-package',source_hash=digest_value,resource_type='report',classification='ordinary',
        classification_confirmed=True,review_state='candidate',audience=payload.audience)
    db.add(policy);db.flush()
    for item in finding_policies:db.add(PolicySource(artifact_id=policy.id,source_id=item.id))
    row=ReleasePackage(policy_id=policy.id,created_by=actor.id,title=payload.title,summary=payload.summary,references_json=canonical(refs),content_hash=digest_value,created_at=clock())
    db.add(row);db.flush()
    from kestrel.services.finding_release_guard import denial
    if denial(db,policy):raise HTTPException(409,'Retained finding restrictions are not bound to this new package')
    event(db,actor,policy,'release.draft',row.id);db.commit();return row,policy

def release_actor(db,actor,request=None):
    from kestrel.models import Account
    from kestrel.repositories.identity import principal
    from kestrel.services.auth import authenticate
    db.expire_all()
    if request is not None:
        fresh=authenticate(db,request)[2]
        if fresh.id!=actor.id:raise HTTPException(403,'Identity changed during release decision')
        return fresh
    account=db.get(Account,actor.id)
    if account is None or not account.active:raise HTTPException(403,'Current firm legal authority required')
    return principal(db,account,clock())


def opaque_retained_revoke(db,actor,row,policy,payload,request=None,*,receipt=False):
    """Tighten access to an unbound artifact without disclosing its content."""
    from kestrel.services.finding_release_guard import pinned_policies
    def current():
        fresh=release_actor(db,actor,request);legal(fresh,policy.matter_id)
        if fresh.id!=row.created_by and R.SME not in fresh.roles:raise HTTPException(403,'Package creator or current Legal SME required for opaque containment')
        return fresh
    fresh=current()
    if payload.content_hash!=row.content_hash or payload.snapshot_hash!=snapshot(db,policy):raise HTTPException(409,'Package or source snapshot changed; refresh')
    if not policy.released:raise HTTPException(409,'Released package required')
    if db.scalar(select(ReleaseApproval.id).where(ReleaseApproval.release_id==row.id,ReleaseApproval.kind=='revoke')):raise HTTPException(409,'Decision already recorded')
    policy.released=False;policy.approved_snapshot_hash=None
    expected=snapshot(db,policy)
    db.add(ReleaseApproval(release_id=row.id,actor_id=fresh.id,kind='revoke',rationale=payload.rationale,content_hash=row.content_hash,snapshot_hash=expected,created_at=clock()))
    captured=pinned_policies(db,row)
    from kestrel.services.content_labels import policy_records
    scopes=set()
    for item in captured:
        if item.classification=='clean_team' and item.clean_team_scope:scopes.add(item.clean_team_scope)
        try:scopes.update(record['scope'] for record in policy_records(db,item.id) if record['scope'])
        except (ValueError,TypeError,KeyError):pass
    if scopes:
        for scope in sorted(scopes):audit(db,'release.revoke','allowed',fresh.id,category='clean_team',matter_id=policy.matter_id,object_id=row.id,clean_team_scope=scope)
    else:event(db,fresh,policy,'release.revoke',row.id)
    db.flush();fresh=current()
    if row.content_hash!=payload.content_hash or snapshot(db,policy)!=expected:raise HTTPException(409,'Package changed before containment receipt')
    db.commit();return {'id':row.id,'revoked':True} if receipt else (row,policy)


def release_decision(db,actor,release_id,operation,payload,request=None,*,receipt=False):
    from kestrel.services.finding_release_guard import denial
    pending=db.scalar(select(ReleasePackage).where(ReleasePackage.id==release_id).with_for_update())
    if pending is None:raise HTTPException(404,'Release unavailable')
    pending_policy=db.get(Policy,pending.policy_id)
    legal(actor,pending_policy.matter_id)
    if denial(db,pending_policy):
        if operation=='revoke':return opaque_retained_revoke(db,actor,pending,pending_policy,payload,request,receipt=receipt)
        raise HTTPException(409,'Retained finding restrictions are not bound to this package; a new governed workflow is required')
    row,policy=package(db,actor,release_id,internal=True,lock=True)
    if operation!='revoke' and actor.id==row.created_by:raise HTTPException(403,'Independent package approver required')
    if payload.content_hash!=row.content_hash or payload.snapshot_hash!=snapshot(db,policy):raise HTTPException(409,'Package or source snapshot changed; refresh')
    sources=lineage(db,policy)
    for source_policy in sources[1:]:require_policy(db,actor,source_policy,'historical_read' if operation=='revoke' else 'read')
    has_ct=any(p.classification=='clean_team' for p in sources)
    previous=list(db.scalars(select(ReleaseApproval).where(ReleaseApproval.release_id==row.id)))
    if any(a.kind==operation for a in previous):raise HTTPException(409,'Decision already recorded')
    if operation=='antitrust':
        if R.ANTITRUST not in actor.roles or not has_ct:raise HTTPException(403,'Named antitrust approval required')
        if policy.released:raise HTTPException(409,'Package already released')
        policy.sanitized=True;policy.antitrust_approved=True
    elif operation=='approve':
        from kestrel.services.ddr_runs import require_internal
        require_internal(db,release_id)
        if policy.released or any(a.kind=='revoke' for a in previous):raise HTTPException(409,'Unreleased package required')
        if any(p.review_state!='reviewed' or p.signing_frozen or p.superseded for p in sources[1:]):raise HTTPException(409,'Eligible reviewed source versions required')
        if has_ct:
            anti=next((a for a in previous if a.kind=='antitrust'),None)
            if not anti or anti.actor_id==actor.id or anti.snapshot_hash!=snapshot(db,policy):raise HTTPException(409,'Separate current antitrust approval required')
        if policy.audience=='castlegate' and any(p.classification=='privileged' or p.resource_type=='legal_advice' for p in sources):raise HTTPException(403,'Bank privilege exclusion')
        configs=list(db.scalars(select(GovernanceVersion).where(GovernanceVersion.matter_id==policy.matter_id,GovernanceVersion.kind=='environment_policy',GovernanceVersion.state=='published')))
        if not configs or any(json.loads(p.definition_json)['block_external'] for p in configs):raise HTTPException(403,'External sharing policy not approved')
        policy.review_state='reviewed';policy.released=True;policy.approved_snapshot_hash=snapshot(db,policy)
    else:
        if not policy.released:raise HTTPException(409,'Released package required')
        policy.released=False;policy.approved_snapshot_hash=None
    db.add(ReleaseApproval(release_id=row.id,actor_id=actor.id,kind=operation,rationale=payload.rationale,content_hash=row.content_hash,snapshot_hash=snapshot(db,policy),created_at=clock()))
    event(db,actor,policy,'release.'+operation,row.id);db.flush()
    expected=snapshot(db,policy)
    output=package_output(db,row,policy,internal=True) if receipt else None
    fresh=release_actor(db,actor,request);legal(fresh,policy.matter_id)
    if operation!='revoke' and fresh.id==row.created_by:raise HTTPException(403,'Independent package approver required')
    if operation=='antitrust' and R.ANTITRUST not in fresh.roles:raise HTTPException(403,'Current named antitrust authority required')
    package(db,fresh,row.id,internal=True)
    current_sources=lineage(db,policy)
    for source_policy in current_sources[1:]:require_policy(db,fresh,source_policy,'historical_read' if operation=='revoke' else 'read')
    if operation!='revoke' and any(p.signing_frozen or p.superseded for p in current_sources):raise HTTPException(409,'Current unfrozen package and sources required')
    if operation=='antitrust' and not any(p.classification=='clean_team' for p in current_sources):raise HTTPException(409,'Current clean-team lineage required for antitrust decision')
    if operation=='approve':
        if any(p.review_state!='reviewed' for p in current_sources[1:]):raise HTTPException(409,'Current reviewed source versions required')
        configs=list(db.scalars(select(GovernanceVersion).where(GovernanceVersion.matter_id==policy.matter_id,GovernanceVersion.kind=='environment_policy',GovernanceVersion.state=='published')))
        if not configs or any(json.loads(p.definition_json)['block_external'] for p in configs):raise HTTPException(403,'Current external sharing policy not approved')
    if snapshot(db,policy)!=expected:raise HTTPException(409,'Package or source snapshot changed before decision receipt')
    db.commit();return output if receipt else (row,policy)


def require_verified_ocr(db,row):
    from kestrel.services.ocr_jobs import verified
    if not verified(db,row):raise HTTPException(409,"Verify the OCR transcript against the original page first")
