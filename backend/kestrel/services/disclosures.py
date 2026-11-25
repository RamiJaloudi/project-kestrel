"""Distinct, validated transcript artifacts. No original-source authorization is relaxed."""
import json
from sqlalchemy import select
from fastapi import HTTPException
from kestrel import models as m
from kestrel.domain import Organization as O,Role as R
from kestrel.repositories.identity import principal
from kestrel.services import workflow as w,review_work as rw,content_labels as labels,diligence,lifecycle
from kestrel.services.auth import clock
from kestrel.adapters.extraction import canonical,digest
from kestrel.adapters import disclosure as tool


def review(db,plan):return db.scalar(select(m.DisclosurePlanReview).where(m.DisclosurePlanReview.plan_id==plan.id))
def decisions(db,a):return list(db.scalars(select(m.DisclosureDecision).where(m.DisclosureDecision.artifact_id==a.id).order_by(m.DisclosureDecision.occurred_at,m.DisclosureDecision.id)))


def internal_plan(db,actor,pid,write=False):
    plan=db.get(m.DisclosurePlan,pid)
    if not plan:raise HTTPException(404,'Disclosure plan unavailable')
    src,policy=rw.source(db,actor,plan.source_id,write);rw.retained(db,actor,plan)
    return plan,src,policy


def current(plan,db,policy):
    if clock()>=plan.expires_at or w.snapshot(db,policy)!=plan.source_snapshot:raise HTTPException(409,'Source attributes changed or disclosure expired; propose a new plan')


def plan_output(db,actor,plan,src,policy):
    r=review(db,plan)
    artifact_id=db.scalar(select(m.DisclosureArtifact.id).where(m.DisclosureArtifact.plan_id==plan.id))
    return {'artifact_id':artifact_id,'id':plan.id,'source_id':src.id,'audience':plan.audience,'title':plan.title,'purpose':plan.purpose,'expires_at':plan.expires_at,'spans':json.loads(plan.spans_json),
        'content_hash':plan.content_hash,'created_by':plan.created_by,'actor_id':actor.id,'can_release':R.SME in actor.roles,'can_antitrust':R.ANTITRUST in actor.roles,
        'state':r.operation if r else 'proposed','stale':w.snapshot(db,policy)!=plan.source_snapshot,'rationale':plan.rationale}


def plans(db,actor,sid):
    src,policy=rw.source(db,actor,sid)
    return [plan_output(db,actor,p,src,policy) for p in db.scalars(select(m.DisclosurePlan).where(m.DisclosurePlan.source_id==sid).order_by(m.DisclosurePlan.created_at.desc()).limit(100))]


def propose(db,actor,p):
    src,policy=rw.source(db,actor,p.source_id,True)
    if src.extraction_status!='ready' or not policy.classification_confirmed:raise HTTPException(409,'Confirmed text-ready source required')
    w.require_verified_ocr(db,src)
    from kestrel.adapters.workbook_safety import handling
    handling(src,policy)
    if p.audience=='castlegate' and (policy.classification=='privileged' or policy.resource_type=='legal_advice'):raise HTTPException(403,'Whole-source legal advice cannot be released to the bank')
    fingerprint=digest(canonical(p.model_dump()).encode())
    old=db.scalar(select(m.DisclosurePlan).where(m.DisclosurePlan.created_by==actor.id,m.DisclosurePlan.request_key==p.request_key))
    if old:
        if old.input_hash!=fingerprint:raise HTTPException(409,'Disclosure request key changed')
        return plan_output(db,actor,old,src,policy)
    spans=[s.model_dump() for s in p.spans];tool.sanitize(src,spans)
    snapshot=w.snapshot(db,policy);created=clock();expiry=created+p.expires_in_days*86400
    material={'source_id':src.id,'source_snapshot':snapshot,'audience':p.audience,'title':p.title,'purpose':p.purpose,'spans':spans,'expires_at':expiry,'created_by':actor.id,'rationale':p.rationale}
    plan=m.DisclosurePlan(**rw.capture(src,policy),audience=p.audience,title=p.title,purpose=p.purpose,expires_at=expiry,spans_json=canonical(spans),source_snapshot=snapshot,
        content_hash=digest(canonical(material).encode()),created_by=actor.id,request_key=p.request_key,input_hash=fingerprint,rationale=p.rationale,created_at=created)
    db.add(plan);db.flush();rw.audit_work(db,actor,policy,'disclosure.plan.propose',plan);db.commit();return plan_output(db,actor,plan,src,policy)


def review_plan(db,actor,pid,p):
    plan,src,policy=internal_plan(db,actor,pid,True);current(plan,db,policy)
    from kestrel.adapters.workbook_safety import handling
    handling(src,policy)
    if actor.id==plan.created_by:raise HTTPException(403,'Independent source-cleared lawyer required')
    if p.content_hash!=plan.content_hash or review(db,plan):raise HTTPException(409,'Exact undecided plan required')
    row=m.DisclosurePlanReview(**rw.capture(src,policy),plan_id=pid,operation=p.operation,content_hash=plan.content_hash,actor_id=actor.id,rationale=p.rationale,occurred_at=clock())
    db.add(row);rw.audit_work(db,actor,policy,'disclosure.plan.'+p.operation,row,[plan]);db.commit();return plan_output(db,actor,plan,src,policy)


def cleared(db,uid,src,required=None):
    account=db.get(m.Account,uid)
    if not account or not account.active:raise HTTPException(403,'Approver authority unavailable')
    actor=principal(db,account,clock());rw.source(db,actor,src.id)
    if required and required not in actor.roles:raise HTTPException(403,'Approver role no longer active')
    return actor


def mask_coverage(db,src,policy,spans,audience):
    sensitive=any(p.classification=='clean_team' for p in w.lineage(db,policy));by={}
    for s in spans:by.setdefault(s['unit'],[]).append((s['start'],s['end']))
    for assertion in labels.rows(db,src.id):
        names,_=labels.checked(db,assertion);names=set(names)
        sensitive=sensitive or bool(names&{'clean_team','competitively_sensitive'})
        restricted=names&{'privileged','clean_team','competitively_sensitive','personal_data','export_controlled'}
        if not restricted:continue
        if assertion.unit_number is None:
            if restricted&{'personal_data','export_controlled'} or ('privileged' in restricted and audience=='castlegate'):raise HTTPException(409,'Whole-document restricted labels require governed scope refinement; no automatic declassification')
            continue
        segments=sorted(by.get(assertion.unit_number,[]));cursor=assertion.start_offset
        for a,b in segments:
            if a<=cursor<b:cursor=b
        if cursor<assertion.end_offset:raise HTTPException(409,'Every restricted passage must be fully removed from this output')
    return bool(sensitive)


def build(db,actor,pid):
    plan,src,policy=internal_plan(db,actor,pid,True);current(plan,db,policy)
    from kestrel.adapters.workbook_safety import handling
    workbook=handling(src,policy)
    old=db.scalar(select(m.DisclosureArtifact).where(m.DisclosureArtifact.plan_id==pid))
    if old:return artifact_output(db,actor,old)
    r=review(db,plan)
    if not r or r.operation!='approve' or r.content_hash!=plan.content_hash:raise HTTPException(409,'Independently approved exact redaction plan required')
    cleared(db,r.actor_id,src)
    whole=diligence.latest_review(db,src.id)
    if not whole or whole.coverage_state!='complete' or policy.review_state!='reviewed':raise HTTPException(409,'Complete whole-document lawyer review required')
    spans=json.loads(plan.spans_json);requires_antitrust=mask_coverage(db,src,policy,spans,plan.audience)
    units,ranges,removed=tool.sanitize(src,spans);data=tool.render(plan.title,units);validation=tool.validate(data,plan.title,units,removed)
    manifest={'schema':'sanitized-transcript-1','plan_id':plan.id,'plan_hash':plan.content_hash,'source_id':src.id,'source_bytes_hash':src.bytes_hash,'source_text_hash':src.text_hash,
        'source_snapshot':plan.source_snapshot,'spans':ranges,'reviewer_id':r.actor_id,'review_rationale':r.rationale,'reviewed_at':r.occurred_at,'generated_at':clock(),'tool':tool.VERSION,
        'requires_antitrust':requires_antitrust,'original_objects_copied':False,'native_office_release':False,'omitted':'All hidden sheets, rows containing hidden cells, formula/cache rows, workbook metadata, original images, attachments, annotations, active content and container objects. Only sanitized extracted text is reconstructed.'}
    if workbook:manifest['workbook_visibility']=workbook['receipt']
    mh=digest(canonical(manifest).encode());bh=digest(data);th=digest(canonical(units).encode());bundle=digest(canonical({'manifest':mh,'bytes':bh,'text':th,'plan':plan.content_hash}).encode())
    derived=m.DocumentPolicyVersion(matter_id=src.matter_id,document_id='sanitized-transcript',source_hash=bh,resource_type='sanitized_document',classification='ordinary',classification_confirmed=True,review_state='candidate',audience=plan.audience,ai_restricted=True)
    db.add(derived);db.flush();db.add(m.PolicySource(artifact_id=derived.id,source_id=policy.id))
    a=m.DisclosureArtifact(**rw.capture(src,policy),plan_id=pid,policy_id=derived.id,data=data,units_json=canonical(units),manifest_json=canonical(manifest),manifest_hash=mh,bytes_hash=bh,text_hash=th,bundle_hash=bundle,created_by=actor.id,created_at=clock())
    db.add(a);db.flush();db.add(m.DisclosureValidation(**rw.capture(src,policy),artifact_id=a.id,bytes_hash=bh,manifest_hash=mh,report_json=canonical(validation),validator_version='rebuilt-pdf-structure-v1',occurred_at=clock()))
    db.flush();rw.audit_work(db,actor,policy,'disclosure.artifact.build',a,[plan,r]);value=artifact_output(db,actor,a);db.commit();return value


def integrity(db,a):
    plan=db.get(m.DisclosurePlan,a.plan_id);manifest=json.loads(a.manifest_json)
    bundle=digest(canonical({'manifest':a.manifest_hash,'bytes':a.bytes_hash,'text':a.text_hash,'plan':plan.content_hash}).encode())
    v=db.scalar(select(m.DisclosureValidation).where(m.DisclosureValidation.artifact_id==a.id))
    if digest(a.data)!=a.bytes_hash or digest(a.units_json.encode())!=a.text_hash or digest(a.manifest_json.encode())!=a.manifest_hash or bundle!=a.bundle_hash:raise HTTPException(403,'Disclosure integrity denied')
    if not v or v.bytes_hash!=a.bytes_hash or v.manifest_hash!=a.manifest_hash or v.validator_version!='rebuilt-pdf-structure-v1':raise HTTPException(403,'Validated artifact required')
    report=json.loads(v.report_json)
    if report.get('passed') is not True or set(report.get('checks',[]))!=set(tool.CHECKS) or report.get('bytes_hash')!=a.bytes_hash:raise HTTPException(403,'Validation evidence denied')
    if manifest.get('source_id')!=a.source_id or plan.source_id!=a.source_id or manifest.get('plan_id')!=plan.id or manifest.get('source_snapshot')!=plan.source_snapshot:raise HTTPException(403,'Disclosure provenance denied')
    from kestrel.adapters.workbook_safety import handling
    source=db.get(m.SourceVersion,a.source_id);parent=db.get(m.DocumentPolicyVersion,source.policy_id)
    try:
        workbook=handling(source,parent)
        if workbook:
            receipt=workbook['receipt'];recorded=manifest.get('workbook_visibility')
            if recorded is not None and recorded!=receipt or (receipt['sensitive_hidden'] or receipt['has_formulas']) and recorded!=receipt:raise HTTPException(403,'Reviewed workbook visibility evidence required')
            if receipt['sensitive_hidden'] and manifest.get('requires_antitrust') is not True:raise HTTPException(403,'Independent workbook handling review required')
            safe,_,_=tool.sanitize(source,json.loads(plan.spans_json))
            if canonical(safe)!=a.units_json:raise HTTPException(403,'Workbook disclosure contains unreviewed hidden or cached content')
    except HTTPException:raise HTTPException(403,'Workbook disclosure safety evidence unavailable; retained records were not changed') from None
    return plan,manifest


def release_ready(db,a,plan,manifest,src):
    rows=decisions(db,a);ops={r.operation:r for r in rows}
    if 'revoke' in ops or 'legal_approve' not in ops or (manifest['requires_antitrust'] and 'antitrust_approve' not in ops):return False
    legal=ops['legal_approve']
    if legal.actor_id in {a.created_by,plan.created_by} or legal.bundle_hash!=a.bundle_hash:return False
    cleared(db,legal.actor_id,src,R.SME)
    if manifest['requires_antitrust']:
        antitrust=ops['antitrust_approve']
        if antitrust.actor_id in {a.created_by,plan.created_by,legal.actor_id} or antitrust.bundle_hash!=a.bundle_hash:return False
        cleared(db,antitrust.actor_id,src,R.ANTITRUST)
    r=review(db,plan)
    if not r or r.operation!='approve' or r.actor_id==plan.created_by:return False
    cleared(db,r.actor_id,src)
    return True


def authorize(db,actor,doc,action,now):
    deny=lambda reason:{'allowed':False,'reason_code':reason,'policy_version':'sanitized-disclosure-1'}
    if action not in {'read','download','historical_read','triage','export_metadata'}:return deny('DISCLOSURE_READ_ONLY')
    a=db.scalar(select(m.DisclosureArtifact).where(m.DisclosureArtifact.policy_id==doc.id))
    if not a:return deny('DISCLOSURE_MISSING')
    try:
        plan,manifest=integrity(db,a);src=db.get(m.SourceVersion,a.source_id);parent=db.get(m.DocumentPolicyVersion,src.policy_id)
        w.source_integrity(src,parent)
        links=list(db.scalars(select(m.PolicySource.source_id).where(m.PolicySource.artifact_id==doc.id)))
        if links!=[parent.id] or doc.matter_id!=src.matter_id or doc.source_hash!=a.bytes_hash or doc.classification!='ordinary' or doc.quarantined or doc.superseded:return deny('DISCLOSURE_LINEAGE_INVALID')
        if actor.org==O.FIRM:
            rw.retained(db,actor,a)
            return {'allowed':True,'reason_code':'INTERNAL_DISCLOSURE_REVIEW','policy_version':'sanitized-disclosure-1'}
        if actor.org not in {O.CLIENT,O.BANK} or action not in {'read','download'}:return deny('ACCESS_DENIED')
        if actor.org.value!=plan.audience or doc.audience!=plan.audience or not doc.released or doc.review_state!='reviewed':return deny('DISCLOSURE_RELEASE_REQUIRED')
        if now>=plan.expires_at or parent.quarantined or parent.superseded or not parent.classification_confirmed or parent.review_state!='reviewed':return deny('DISCLOSURE_STALE')
        if actor.org==O.BANK and (parent.classification=='privileged' or parent.resource_type=='legal_advice'):return deny('BANK_PRIVILEGE')
        if w.snapshot(db,parent)!=plan.source_snapshot or doc.approved_snapshot_hash!=w.snapshot(db,doc):return deny('DISCLOSURE_STALE')
        if not release_ready(db,a,plan,manifest,src):return deny('DISCLOSURE_APPROVAL_REQUIRED')
        return {'allowed':True,'reason_code':'APPROVED_SANITIZED_DISCLOSURE','policy_version':'sanitized-disclosure-1'}
    except (HTTPException,ValueError,TypeError,KeyError):return deny('DISCLOSURE_VALIDATION_DENIED')


def read(db,actor,aid):
    a=db.get(m.DisclosureArtifact,aid)
    if not a:raise HTTPException(404,'Disclosure unavailable')
    policy=db.get(m.DocumentPolicyVersion,a.policy_id);w.require_policy(db,actor,policy)
    return a,policy


def artifact_output(db,actor,a):
    _,policy=read(db,actor,a.id);plan,manifest=integrity(db,a)
    value={'id':a.id,'title':plan.title,'audience':plan.audience,'purpose':plan.purpose,'expires_at':plan.expires_at,'bytes_hash':a.bytes_hash,'released':policy.released and not any(d.operation=='revoke' for d in decisions(db,a)),'format':'pdf','description':'Sanitized text transcript; original layout, images and attachments omitted.'}
    if actor.org==O.FIRM:value.update({'source_id':a.source_id,'bundle_hash':a.bundle_hash,'manifest':manifest,'created_by':a.created_by,'plan_author_id':plan.created_by,'requires_antitrust':manifest['requires_antitrust'],'decisions':[{'operation':d.operation,'actor_id':d.actor_id,'rationale':d.rationale} for d in decisions(db,a)]})
    return value


def listing(db,actor,matter):
    if actor.org==O.FIRM:rw.internal(actor)
    from kestrel.domain import member_and_not_walled
    if not member_and_not_walled(actor,matter):raise HTTPException(403,'Matter denied')
    result=[]
    for a in db.scalars(select(m.DisclosureArtifact).where(m.DisclosureArtifact.matter_id==matter).order_by(m.DisclosureArtifact.created_at.desc()).limit(500)):
        try:result.append(artifact_output(db,actor,a))
        except HTTPException as e:
            if e.status_code not in {403,404}:raise
    return result


def decide(db,actor,aid,p):
    a,derived=read(db,actor,aid);plan,manifest=integrity(db,a)
    src,parent=rw.source(db,actor,a.source_id,p.operation!='revoke')
    if p.bundle_hash!=a.bundle_hash:raise HTTPException(409,'Exact validated artifact bundle required')
    ops={d.operation:d for d in decisions(db,a)}
    if p.operation in ops or 'revoke' in ops:raise HTTPException(409,'Decision already recorded or artifact revoked')
    if p.operation=='revoke':
        if R.SME not in actor.roles and R.ANTITRUST not in actor.roles:raise HTTPException(403,'Scoped senior lawyer or antitrust counsel required')
    else:
        current(plan,db,parent)
        if actor.id in {a.created_by,plan.created_by}:raise HTTPException(403,'Independent release approver required')
        if p.operation=='legal_approve' and R.SME not in actor.roles:raise HTTPException(403,'Scoped senior lawyer required')
        if p.operation=='antitrust_approve':
            if R.ANTITRUST not in actor.roles or (ops.get('legal_approve') and ops['legal_approve'].actor_id==actor.id):raise HTTPException(403,'Separate independent antitrust counsel required')
        if p.operation=='legal_approve' and ops.get('antitrust_approve') and ops['antitrust_approve'].actor_id==actor.id:raise HTTPException(403,'Legal and antitrust approvers must differ')
    row=m.DisclosureDecision(**rw.capture(src,parent),artifact_id=aid,operation=p.operation,bundle_hash=a.bundle_hash,actor_id=actor.id,rationale=p.rationale,occurred_at=clock());db.add(row);db.flush()
    if p.operation!='revoke' and release_ready(db,a,plan,manifest,src):
        derived.review_state='reviewed';derived.released=True;derived.sanitized=True;derived.antitrust_approved=manifest['requires_antitrust'];db.flush();derived.approved_snapshot_hash=w.snapshot(db,derived)
    rw.audit_work(db,actor,parent,'disclosure.'+p.operation,row,[a,plan]);db.flush();value=artifact_output(db,actor,a);db.commit();return value


def reader(db,actor,aid):
    from kestrel.adapters.citation_anchors import anchors
    a,policy=read(db,actor,aid);p=db.get(m.DisclosurePlan,a.plan_id)
    w.event(db,actor,policy,'disclosure.reader',a.id);db.commit()
    return {'id':a.id,'file_name':p.title,'version_number':1,'bytes_hash':a.bytes_hash,'snapshot_hash':w.snapshot(db,policy),'classification':'sanitized transcript','language':'Original-language excerpts','governing_law':'See approved transcript','extraction_status':'ready','format':'pdf','citation_anchors':anchors(json.loads(a.units_json),artifact_id=a.id),'units':json.loads(a.units_json),'blocks':[],'sheets':[],'can_classify_content':False}
