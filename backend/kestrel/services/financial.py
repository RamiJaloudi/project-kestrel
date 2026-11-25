"""Human-evidenced numeric facts. Access is checked before amounts, counts or arithmetic."""
import json
from decimal import Decimal
from sqlalchemy import select
from fastapi import HTTPException
from kestrel import models as m
from kestrel.domain import Organization as O,Role as R,member_and_not_walled
from kestrel.services import workflow as w,review_work as rw,questions as q,disclosures as disclosure,lifecycle
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest
from kestrel.adapters.financial import number,base_amount,canonical_amount,compare


def reference(db,actor,kind,rid,write=False):
    if kind=='source':
        src,policy=rw.source(db,actor,rid,write)
        if not policy.classification_confirmed or src.extraction_status!='ready':raise HTTPException(409,'Confirmed text-ready source required')
        w.require_verified_ocr(db,src)
        return src,policy,json.loads(src.units_json)
    artifact,policy=disclosure.read(db,actor,rid)
    src=db.get(m.SourceVersion,artifact.source_id)
    if write:rw.source(db,actor,src.id,True)
    return src,policy,json.loads(artifact.units_json)


def gate_row(db,matter):return db.scalar(select(m.FinancialAccessGate).where(m.FinancialAccessGate.matter_id==matter).order_by(m.FinancialAccessGate.revision.desc()).limit(1))

def organization_gate(db,actor,p=None):
    if actor.org!=O.FIRM or R.ROOT_ADMIN not in actor.roles:raise HTTPException(403,'Root administrative configuration required')
    org=db.scalar(select(m.Organization).where(m.Organization.code=='castlegate').with_for_update())
    if not org:raise HTTPException(409,'Bank organization unavailable')
    old=db.scalar(select(m.FinancialOrganizationGate).where(m.FinancialOrganizationGate.organization_id==org.id).order_by(m.FinancialOrganizationGate.revision.desc()))
    if p:
        if p.expected_revision!=(old.revision if old else 0):raise HTTPException(409,'Organization financial gate changed')
        old=m.FinancialOrganizationGate(organization_id=org.id,revision=p.expected_revision+1,enabled=p.enabled,actor_id=actor.id,rationale=p.rationale,occurred_at=clock());db.add(old)
        audit(db,'financial.bank_organization_gate','allowed',actor.id,category='administrative');db.commit()
    return {'organization':'castlegate','revision':old.revision if old else 0,'enabled':bool(old and old.enabled)}

def require_bank_gate(db,matter):
    org=db.scalar(select(m.Organization).where(m.Organization.code=='castlegate'))
    organization=db.scalar(select(m.FinancialOrganizationGate).where(m.FinancialOrganizationGate.organization_id==org.id).order_by(m.FinancialOrganizationGate.revision.desc())) if org else None
    gate=gate_row(db,matter)
    if not organization or not organization.enabled or not gate or not gate.enabled:raise HTTPException(403,'Bank financial dashboard disabled')


def gate_access(actor,matter):
    if actor.org!=O.FIRM or R.ROOT_ADMIN not in actor.roles or not member_and_not_walled(actor,matter):raise HTTPException(403,'Scoped administrative configuration required')


def gate(db,actor,matter,p=None):
    gate_access(actor,matter)
    db.scalar(select(m.Matter).where(m.Matter.id==matter).with_for_update())
    old=gate_row(db,matter)
    if p:
        if p.expected_revision!=(old.revision if old else 0):raise HTTPException(409,'Financial gate changed; refresh first')
        # Disabling remains possible after signing; it grants no content access.
        if p.enabled:lifecycle.mutable(db,matter)
        old=m.FinancialAccessGate(matter_id=matter,revision=p.expected_revision+1,enabled=p.enabled,actor_id=actor.id,rationale=p.rationale,occurred_at=clock());db.add(old)
        audit(db,'financial.bank_gate','allow',actor.id,matter_id=matter,category='administrative');db.commit()
    return {'revision':old.revision if old else 0,'enabled':bool(old and old.enabled)}


def history(db,f):return list(db.scalars(select(m.FinancialFactDecision).where(m.FinancialFactDecision.fact_id==f.id).order_by(m.FinancialFactDecision.occurred_at,m.FinancialFactDecision.id)))


def read(db,actor,f):
    q.access(actor,f.matter_id,db)
    if actor.org==O.BANK:
        require_bank_gate(db,f.matter_id)
    src,policy,units=reference(db,actor,f.reference_kind,f.reference_id)
    if w.snapshot(db,policy)!=f.reference_snapshot:raise HTTPException(403,'Financial evidence attributes changed; propose a new fact')
    if actor.org==O.FIRM:rw.retained(db,actor,f)
    else:
        if f.reference_kind!='derivative':raise HTTPException(403,'Original-source financial facts are internal only')
        decisions=history(db,f);ops={d.operation for d in decisions}
        if not {'verify','release'}<=ops or ops&{'reject','revoke'}:raise HTTPException(403,'Financial fact not released')
        for d in decisions:
            if d.operation in {'verify','release'}:
                reviewer=disclosure.cleared(db,d.actor_id,src,R.SME if d.operation=='release' else None)
                reference(db,reviewer,f.reference_kind,f.reference_id)
    return src,policy,units


def output(db,actor,f,*,view_action='financial.fact_view'):
    _,policy,_=read(db,actor,f);e=json.loads(f.evidence_json);ops={d.operation for d in history(db,f)}
    value={k:getattr(f,k) for k in ['id','entity','metric','period_start','period_end','currency','scale','accounting_basis','consolidation_scope','amount_text','content_hash']}
    value.update({'state':'revoked' if 'revoke' in ops else 'rejected' if 'reject' in ops else 'released' if 'release' in ops else 'verified' if 'verify' in ops else 'proposed',
        'evidence':e,'reader':{'id':f.reference_id,**({'kind':'disclosure'} if f.reference_kind=='derivative' else {}),'unit':e['unit'],'start':e['start'],'end':e['end']}})
    value['supporting_evidence']=[{'label':c['locator'],'text':c['text'],'reader':{**value['reader'],'unit':c['unit'],'start':c['start'],'end':c['end']}} for c in e.get('dimension_contexts',[])]
    if actor.org==O.FIRM:value.update({'created_by':f.created_by,'actor_id':actor.id,'can_release':R.SME in actor.roles,'reference_kind':f.reference_kind})
    w.event(db,actor,policy,view_action,f.id)
    return value


def propose(db,actor,p):
    rw.internal(actor);src,policy,units=reference(db,actor,p.reference_kind,p.reference_id,True)
    unit=next((u for u in units if u['number']==p.unit),None)
    if p.context_end-p.context_start>8000:raise HTTPException(422,'Select a financial evidence context of at most 8000 Unicode characters')
    if not unit or p.context_end>len(unit['text']):raise HTTPException(422,'Evidence offsets exceed the extracted source')
    context=unit['text'][p.context_start:p.context_end]
    if unit['text'][p.start:p.end]!=p.raw_number:raise HTTPException(422,'Numeric token differs from exact source evidence')
    contexts=[]
    for span in p.context_spans:
        other=next((u for u in units if u['number']==span.unit),None)
        if not other or not 0<=span.start<span.end<=len(other['text']):raise HTTPException(422,'Exact dimensional evidence range required')
        contexts.append({'unit':span.unit,'start':span.start,'end':span.end,'locator':other['locator'],'text':other['text'][span.start:span.end]})
    if len(context)+sum(len(c['text']) for c in contexts)>8000:raise HTTPException(422,'Combined financial evidence context exceeds 8000 Unicode characters')
    for field in ['entity','metric','period_label','currency','scale_label','accounting_basis','consolidation_scope']:
        if not any(getattr(p,field) in c for c in [context,*[x['text'] for x in contexts]]):raise HTTPException(422,'Every dimension must have literal supporting evidence in the selected contexts')
    amount=base_amount(number(p.raw_number,p.decimal_mark,scientific=p.numeric_notation=='scientific'),p.scale)
    evidence={'unit':p.unit,'start':p.start,'end':p.end,'raw_number':p.raw_number,'decimal_mark':p.decimal_mark,'numeric_notation':p.numeric_notation,'context_start':p.context_start,'context_end':p.context_end,'context':context,'dimension_contexts':contexts,'period_label':p.period_label,'scale_label':p.scale_label,'locator':unit['locator']}
    material=p.model_dump(mode='json');material.update({'reference_snapshot':w.snapshot(db,policy),'amount':canonical_amount(amount),'extractor':'human-exact-2'})
    anchor={k:v for k,v in material.items() if k not in {'context_start','context_end','context_spans','period_label','scale_label','decimal_mark'}}
    key=digest(canonical(anchor).encode());content_hash=digest(canonical(material).encode());old=db.scalar(select(m.FinancialFact).where(m.FinancialFact.evidence_key==key))
    if old:
        if old.content_hash!=content_hash:raise HTTPException(409,'This exact financial anchor and dimensions already have retained evidence; duplicates do not multiply values')
        return output(db,actor,old)
    # Retained restrictions come from the original, even for a sanitized derivative.
    parent=db.get(m.DocumentPolicyVersion,src.policy_id)
    f=m.FinancialFact(**rw.capture(src,parent),evidence_key=key,reference_kind=p.reference_kind,reference_id=p.reference_id,reference_snapshot=w.snapshot(db,policy),
        entity=p.entity,metric=p.metric,period_start=p.period_start.isoformat(),period_end=p.period_end.isoformat(),currency=p.currency,scale=p.scale,
        accounting_basis=p.accounting_basis,consolidation_scope=p.consolidation_scope,amount=amount,amount_text=canonical_amount(amount),evidence_json=canonical(evidence),content_hash=content_hash,created_by=actor.id,created_at=clock())
    db.add(f);db.flush();rw.audit_work(db,actor,parent,'financial.propose',f);value=output(db,actor,f);db.commit();return value


def decide(db,actor,fid,p):
    f=db.get(m.FinancialFact,fid)
    if not f:raise HTTPException(404,'Financial fact unavailable')
    w.legal(actor,f.matter_id)
    db.scalar(select(m.FinancialFact).where(m.FinancialFact.id==fid).with_for_update())
    src,policy,_=read(db,actor,f)
    if p.operation!='revoke':lifecycle.mutable(db,f.matter_id)
    if p.content_hash!=f.content_hash:raise HTTPException(409,'Exact financial fact version required')
    ops={d.operation for d in history(db,f)}
    if p.operation in ops or ops&{'reject','revoke'}:raise HTTPException(409,'Financial decision already closed')
    if p.operation in {'verify','reject','release'} and actor.id==f.created_by:raise HTTPException(403,'Independent reviewer required')
    if p.operation=='release':
        if R.SME not in actor.roles or 'verify' not in ops:raise HTTPException(403,'Independent SME release after verification required')
        if f.reference_kind!='derivative':raise HTTPException(409,'External financial release requires a separately approved sanitized derivative')
        for d in history(db,f):
            if d.operation=='verify':disclosure.cleared(db,d.actor_id,src)
        artifact=db.get(m.DisclosureArtifact,f.reference_id);plan,manifest=disclosure.integrity(db,artifact)
        if clock()>=plan.expires_at or w.snapshot(db,db.get(m.DocumentPolicyVersion,src.policy_id))!=plan.source_snapshot:raise HTTPException(409,'Sanitized derivative is expired or stale')
        if not policy.released or not disclosure.release_ready(db,artifact,plan,manifest,src):raise HTTPException(409,'Sanitized derivative requires its own current independent release first')
    if p.operation=='reject' and 'verify' in ops:raise HTTPException(409,'Verified facts require explicit revocation')
    if p.operation=='revoke' and R.SME not in actor.roles:raise HTTPException(403,'SME revocation required')
    row=m.FinancialFactDecision(**rw.capture(src,db.get(m.DocumentPolicyVersion,src.policy_id)),fact_id=f.id,operation=p.operation,content_hash=f.content_hash,actor_id=actor.id,rationale=p.rationale,occurred_at=clock())
    db.add(row);db.flush();rw.audit_work(db,actor,policy,'financial.'+p.operation,row);value=output(db,actor,f);db.commit();return value


def query(db,actor,p,*,view_action='financial.fact_view'):
    q.access(actor,p.matter_id,db)
    if actor.org==O.BANK:
        require_bank_gate(db,p.matter_id)
    stmt=select(m.FinancialFact).where(m.FinancialFact.matter_id==p.matter_id)
    for field in ['entity','metric','currency','period_start','period_end']:
        value=getattr(p,field)
        if value is not None:stmt=stmt.where(getattr(m.FinancialFact,field)==str(value))
    if db.bind.dialect.name!='sqlite':
        if p.minimum is not None:stmt=stmt.where(m.FinancialFact.amount>=Decimal(p.minimum))
        if p.maximum is not None:stmt=stmt.where(m.FinancialFact.amount<=Decimal(p.maximum))
    rows=[];truncated=False
    for f in db.scalars(stmt.order_by(m.FinancialFact.created_at,m.FinancialFact.id)):
        try:
            read(db,actor,f)
            if p.minimum is not None and f.amount<Decimal(p.minimum):continue
            if p.maximum is not None and f.amount>Decimal(p.maximum):continue
            if len(rows)>=100:truncated=True;break
            rows.append(output(db,actor,f,view_action=view_action))
        except HTTPException as error:
            if error.status_code!=403:raise
    db.commit();return {'route':'typed_financial_sql','rows':rows,'authorized_count':len(rows),'truncated':truncated,'calculation':'No aggregation across facts, periods, currencies or accounting scopes'}


def reconcile(db,actor,p):
    pair=[db.get(m.FinancialFact,x) for x in [p.left_id,p.right_id]]
    if not all(pair):raise HTTPException(404,'Financial comparison unavailable')
    for f in pair:read(db,actor,f)
    a,b=pair;dimensions=['matter_id','entity','metric','period_start','period_end','currency','accounting_basis','consolidation_scope']
    if any(getattr(a,k)!=getattr(b,k) for k in dimensions):raise HTTPException(409,'Incomparable financial dimensions; no inferred FX, period or accounting conversion')
    if any(not {'verify'}<={d.operation for d in history(db,f)} or {d.operation for d in history(db,f)}&{'reject','revoke'} for f in pair):raise HTTPException(409,'Two verified, active facts required')
    result={'status':'consistent' if a.amount==b.amount else 'conflict_requires_review','currency':a.currency,'left':output(db,actor,a),'right':output(db,actor,b),'calculation':{'operator':'subtract_and_percent_against_absolute_right','inputs':[a.id,b.id],**compare(a.amount_text,b.amount_text)},'resolution':'No automatic choice of authoritative source'}
    if actor.org==O.FIRM and a.amount!=b.amount:
        lifecycle.mutable(db,a.matter_id)
        key=digest(canonical(sorted([a.content_hash,b.content_hash])).encode())
        case=db.scalar(select(m.FinancialReconciliation).where(m.FinancialReconciliation.content_hash==key))
        if not case:
            case=m.FinancialReconciliation(matter_id=a.matter_id,left_id=a.id,right_id=b.id,content_hash=key,calculation_json=canonical(result['calculation']),created_by=actor.id,created_at=clock());db.add(case);db.flush()
            for f in pair:w.event(db,actor,read(db,actor,f)[1],'financial.conflict_detected',case.id)
        result['case']=case_output(db,actor,case)
    db.commit();return result


def case_output(db,actor,case):
    left=db.get(m.FinancialFact,case.left_id);right=db.get(m.FinancialFact,case.right_id)
    for f in [left,right]:read(db,actor,f)
    r=db.scalar(select(m.FinancialResolution).where(m.FinancialResolution.reconciliation_id==case.id))
    result={'id':case.id,'content_hash':case.content_hash,'left':output(db,actor,left),'right':output(db,actor,right),'calculation':json.loads(case.calculation_json),'status':r.operation if r else 'awaiting_independent_resolution'}
    if actor.org==O.FIRM:result.update({'created_by':case.created_by,'actor_id':actor.id,'can_resolve':R.SME in actor.roles,'rationale':r.rationale if r else None})
    return result


def cases(db,actor,matter):
    q.access(actor,matter,db);rows=[]
    if actor.org!=O.FIRM:raise HTTPException(403,'Internal reconciliation assessments require a separate publication workflow')
    for case in db.scalars(select(m.FinancialReconciliation).where(m.FinancialReconciliation.matter_id==matter).order_by(m.FinancialReconciliation.created_at.desc())):
        try:
            value=case_output(db,actor,case)
            if len(rows)>=100:break
            rows.append(value)
        except HTTPException as error:
            if error.status_code!=403:raise
    db.commit();return rows


def resolve(db,actor,cid,p):
    case=db.scalar(select(m.FinancialReconciliation).where(m.FinancialReconciliation.id==cid).with_for_update())
    if not case:raise HTTPException(404,'Reconciliation unavailable')
    w.legal(actor,case.matter_id);case_output(db,actor,case);lifecycle.mutable(db,case.matter_id)
    if R.SME not in actor.roles or actor.id==case.created_by:raise HTTPException(403,'Independent source-cleared SME required')
    if p.content_hash!=case.content_hash or db.scalar(select(m.FinancialResolution.id).where(m.FinancialResolution.reconciliation_id==cid)):raise HTTPException(409,'Exact unresolved comparison required')
    for fid in [case.left_id,case.right_id]:
        f=db.get(m.FinancialFact,fid);ops={d.operation for d in history(db,f)}
        if 'verify' not in ops or ops&{'reject','revoke'}:raise HTTPException(409,'Comparison facts no longer eligible')
        w.event(db,actor,read(db,actor,f)[1],'financial.conflict_resolve',case.id)
    db.add(m.FinancialResolution(matter_id=case.matter_id,reconciliation_id=cid,operation=p.operation,content_hash=case.content_hash,actor_id=actor.id,rationale=p.rationale,occurred_at=clock()));db.flush()
    value=case_output(db,actor,case);db.commit();return value


def answer(db,actor,p):
    from kestrel.schemas.financial import Query
    if p.financial_filters is None:raise HTTPException(422,'Supply explicit typed financial filters; the system does not infer currency, scale or fiscal periods from your question')
    result=query(db,actor,Query(matter_id=p.matter_id,**p.financial_filters.model_dump()))
    verified=[f for f in result['rows'] if f['state'] in {'verified','released'}];refs=[]
    for f in verified:
        fact=db.get(m.FinancialFact,f['id']);_,policy,_=read(db,actor,fact)
        refs.append({'kind':'financial','object_id':f['id'],'snapshot':w.snapshot(db,policy),'label':f"{f['entity']} · {f['metric']} · {f['currency']} {f['amount_text']} · {f['period_start']}–{f['period_end']}",
            'text':f['evidence']['context'],'reader':f['reader'],'supporting_evidence':f['supporting_evidence']})
    selected=refs[:p.top_k]
    value={'mode':'typed_financial_evidence','status':'evidence_found' if selected else 'insufficient_evidence','answer':'\n'.join(f"[{i+1}] {r['label']}" for i,r in enumerate(selected)) if selected else 'No eligible verified financial facts match these explicit filters.',
        'citations':selected,'_scope_refs':q.scope_refs(refs),'coverage':'Verified facts only, up to 100 permission-filtered candidates and the chosen citation limit. No summation, inferred FX, inferred fiscal period or LLM arithmetic. Interpret the source evidence with a reviewer.',
        'retrieval':{'route':'typed_financial_sql','ranker':'exact typed filters, stable created-at/ID order','reason':'Explicit financial filters selected the verified fact store. Free-text questions do not invent numeric dimensions.','authorized_chunks':len(refs),'truncated':result['truncated'],'requested_mode':p.mode}}
    return q.save(db,actor,p,value)
