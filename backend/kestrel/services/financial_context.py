"""Internal source-bound sidecars. Neither confirmation nor scanning releases facts."""
import json
from sqlalchemy import select
from fastapi import HTTPException
from kestrel import models as m
from kestrel.domain import Role as R
from kestrel.repositories.identity import principal
from kestrel.schemas.financial_context import Dimensions
from kestrel.services import financial as finance,workflow as w,review_work as rw,lifecycle
from kestrel.services.auth import clock,audit
from kestrel.adapters.extraction import canonical,digest
from kestrel.adapters.financial import compare as arithmetic

FIELDS=['instruments','precision','sign','calendar','period','restatement']
VERSION='financial-context-1'

def internal(actor):rw.internal(actor)

def source_captures(db,actor,rows):
    seen=set()
    for row in rows:
        if row is None:raise HTTPException(403,'Retained financial provenance unavailable')
        key=(row.source_id,row.retained_classification,row.retained_scope)
        if key not in seen:rw.retained(db,actor,row);seen.add(key)

def fact(db,actor,fid,write=False):
    internal(actor);row=db.get(m.FinancialFact,fid)
    if not row:raise HTTPException(404,'Financial fact unavailable')
    src,policy,units=finance.read(db,actor,row)
    if write:
        db.scalar(select(m.Matter).where(m.Matter.id==row.matter_id).with_for_update());lifecycle.mutable(db,row.matter_id)
    return row,src,policy,units

def latest(db,fid):return db.scalar(select(m.FinancialFactContext).where(m.FinancialFactContext.fact_id==fid).order_by(m.FinancialFactContext.revision.desc()).limit(1))
def evidence(db,cid):return list(db.scalars(select(m.FinancialContextEvidence).where(m.FinancialContextEvidence.context_id==cid).order_by(m.FinancialContextEvidence.field,m.FinancialContextEvidence.unit_number,m.FinancialContextEvidence.start_offset,m.FinancialContextEvidence.end_offset)))
def decisions(db,cid):return list(db.scalars(select(m.FinancialContextDecision).where(m.FinancialContextDecision.context_id==cid).order_by(m.FinancialContextDecision.occurred_at,m.FinancialContextDecision.id)))

def audit_records(db,object_id):
    direct=db.get(m.FinancialExtractionCandidate,object_id)
    if direct:return [direct]
    context=db.get(m.FinancialFactContext,object_id);entry=None
    if not context:
        for model in [m.FinancialContextEvidence,m.FinancialContextDecision]:
            entry=db.get(model,object_id)
            if entry:context=db.get(m.FinancialFactContext,entry.context_id);break
    if not context:return []
    # The original fact may retain a DIFFERENT historic clean-team scope from
    # the current source and this sidecar. Every audit/signing read needs both.
    rows=[context,db.get(m.FinancialFact,context.fact_id),*evidence(db,context.id),*decisions(db,context.id)]
    return rows

def material(context,refs):
    fields=['matter_id','source_id','retained_classification','retained_scope','fact_id','revision','previous_hash','fact_hash','reference_kind','reference_id','reference_snapshot','dimensions_json','provenance_json','rationale','created_by','created_at']
    return {**{name:getattr(context,name) for name in fields},'evidence':[{name:getattr(ref,name) for name in ['source_id','retained_classification','retained_scope','field','unit_number','start_offset','end_offset','quote','quote_hash']} for ref in refs]}

def integrity(db,context,row,units):
    refs=evidence(db,context.id)
    if context.fact_hash!=row.content_hash or context.matter_id!=row.matter_id or context.source_id!=row.source_id or (context.reference_kind,context.reference_id,context.reference_snapshot)!=(row.reference_kind,row.reference_id,row.reference_snapshot):raise HTTPException(403,'Financial context reference integrity denied')
    if digest(canonical(material(context,refs)).encode())!=context.content_hash:raise HTTPException(403,'Financial context integrity denied')
    by={u['number']:u for u in units}
    for ref in refs:
        unit=by.get(ref.unit_number)
        if ref.source_id!=context.source_id or ref.matter_id!=context.matter_id or not unit or unit['text'][ref.start_offset:ref.end_offset]!=ref.quote or digest(ref.quote.encode())!=ref.quote_hash:raise HTTPException(403,'Financial context evidence integrity denied')
    try:return Dimensions.model_validate_json(context.dimensions_json)
    except Exception:raise HTTPException(403,'Financial context dimensions denied')

def read(db,actor,cid):
    internal(actor);context=db.get(m.FinancialFactContext,cid)
    if not context:raise HTTPException(404,'Financial context unavailable')
    row,src,policy,units=fact(db,actor,context.fact_id)
    dimensions=integrity(db,context,row,units);source_captures(db,actor,audit_records(db,cid))
    return context,row,src,policy,units,dimensions

def active_fact(db,row):
    ops={entry.operation for entry in finance.history(db,row)}
    return 'verify' in ops and not ops&{'reject','revoke'}

def state(db,context):
    ops={entry.operation for entry in decisions(db,context.id)}
    return 'REVOKED' if 'revoke' in ops else 'REJECTED' if 'reject' in ops else 'CONFIRMED' if 'confirm' in ops else 'PROPOSED'

def confirmed(db,context,row):
    if state(db,context)!='CONFIRMED' or not active_fact(db,row):return False
    decision=next(entry for entry in decisions(db,context.id) if entry.operation=='confirm')
    if decision.content_hash!=context.content_hash or not decision.content_reviewed or decision.actor_id in {context.created_by,row.created_by}:return False
    account=db.get(m.Account,decision.actor_id)
    if not account or not account.active:return False
    reviewer=principal(db,account,clock())
    if R.SME not in reviewer.roles:return False
    try:read(db,reviewer,context.id)
    except HTTPException:return False
    return True

def output(db,actor,context):
    context,row,src,policy,units,dimensions=read(db,actor,context.id)
    current=state(db,context)
    if current=='CONFIRMED' and not confirmed(db,context,row):current='CONFIRMATION_STALE'
    refs=evidence(db,context.id)
    rw.audit_work(db,actor,db.get(m.DocumentPolicyVersion,src.policy_id),'financial_context.read',context,audit_records(db,context.id))
    return {'id':context.id,'fact_id':row.id,'matter_id':context.matter_id,'revision':context.revision,'content_hash':context.content_hash,'previous_hash':context.previous_hash,'fact_hash':context.fact_hash,
        'state':current,'dimensions':dimensions.model_dump(mode='json'),'provenance':json.loads(context.provenance_json),'rationale':context.rationale,'created_by':context.created_by,'created_at':context.created_at,
        'actor_id':actor.id,'can_confirm':R.SME in actor.roles and actor.id not in {context.created_by,row.created_by} and current=='PROPOSED' and active_fact(db,row),
        'can_revoke':actor.id==context.created_by or R.SME in actor.roles,
        'evidence':[{'field':ref.field,'unit':ref.unit_number,'start':ref.start_offset,'end':ref.end_offset,'quote':ref.quote,'quote_hash':ref.quote_hash,
            'reader':{'id':row.reference_id,**({'kind':'disclosure'} if row.reference_kind=='derivative' else {}),'unit':ref.unit_number,'start':ref.start_offset,'end':ref.end_offset}} for ref in refs],
        'decisions':[{'operation':entry.operation,'actor_id':entry.actor_id,'rationale':entry.rationale,'occurred_at':entry.occurred_at} for entry in decisions(db,context.id)],
        'audience':'internal_only','publication':'No context is included in released financial fact output; separate context publication is not implemented.'}

def fact_view(db,actor,fid):
    row,src,policy,units=fact(db,actor,fid)
    contexts=list(db.scalars(select(m.FinancialFactContext).where(m.FinancialFactContext.fact_id==fid).order_by(m.FinancialFactContext.revision.desc()).limit(101)))
    if len(contexts)>100:raise HTTPException(413,'Financial context history exceeds the local 100-version limit')
    values=[output(db,actor,context) for context in contexts]
    return {'fact_id':row.id,'matter_id':row.matter_id,'fact_hash':row.content_hash,'fact_created_by':row.created_by,'actor_id':actor.id,'underlying_verified':active_fact(db,row),
        'current':values[0] if values else None,'history':values,'units':[{'number':u['number'],'locator':u['locator'],'text':u['text']} for u in units],
        'reference':{'kind':row.reference_kind,'id':row.reference_id},'audience':'internal_only'}

def literals(dimensions,field):
    value=getattr(dimensions,field)
    if value.status!='KNOWN':return []
    if field=='instruments':return [item for identifier in value.identifiers for item in [identifier.value,identifier.venue] if item]
    if field=='precision':return [value.label,*([value.value] if value.value else [])]
    if field=='sign':return [value.convention]
    return [value.label]

def sign_presentation(raw):
    raw=raw.strip()
    return 'parentheses' if raw.startswith('(') and raw.endswith(')') else 'minus' if raw.startswith('-') else 'plus' if raw.startswith('+') else 'unsigned'

def validate_evidence(p,units,row):
    by={unit['number']:unit for unit in units};grouped={field:[] for field in FIELDS};refs=[];total=0
    for selected in p.evidence:
        unit=by.get(selected.unit)
        if not unit or selected.end>len(unit['text']):raise HTTPException(422,'Context evidence must match an exact retained source range')
        quote=unit['text'][selected.start:selected.end];total+=len(quote)
        if total>8000:raise HTTPException(422,'Combined financial context evidence exceeds 8000 characters')
        grouped[selected.field].append(quote);refs.append((selected,quote))
    for field in FIELDS:
        dimension=getattr(p.dimensions,field)
        if dimension.status=='UNKNOWN':
            if grouped[field]:raise HTTPException(422,'Unknown fields cannot imply supported values; clear their evidence or explicitly propose the dimension')
            continue
        if not grouped[field] or any(not any(value in quote for quote in grouped[field]) for value in literals(p.dimensions,field)):raise HTTPException(422,'Every known context value needs exact supporting evidence for its field')
    if p.dimensions.sign.status=='KNOWN' and p.dimensions.sign.presentation!=sign_presentation(json.loads(row.evidence_json)['raw_number']):raise HTTPException(422,'Sign presentation differs from the underlying immutable numeric token')
    return refs

def propose(db,actor,fid,p):
    row,src,policy,units=fact(db,actor,fid,True);fingerprint=rw.fingerprint(p)
    old=db.scalar(select(m.FinancialFactContext).where(m.FinancialFactContext.created_by==actor.id,m.FinancialFactContext.request_key==p.request_key))
    if old:
        if old.fact_id!=fid or old.input_hash!=fingerprint:raise HTTPException(409,'Financial context request key changed')
        return output(db,actor,old)
    prior=latest(db,fid)
    if (prior.content_hash if prior else None)!=p.expected_context_hash:raise HTTPException(409,'Financial context changed; load the current exact version')
    if prior and prior.revision>=100:raise HTTPException(413,'Local financial context history is limited to 100 versions')
    selected=validate_evidence(p,units,row);parent=db.get(m.DocumentPolicyVersion,src.policy_id);capture=rw.capture(src,parent)
    refs=[m.FinancialContextEvidence(**capture,field=span.field,unit_number=span.unit,start_offset=span.start,end_offset=span.end,quote=quote,quote_hash=digest(quote.encode())) for span,quote in selected]
    refs.sort(key=lambda ref:(ref.field,ref.unit_number,ref.start_offset,ref.end_offset))
    provenance={'schema':VERSION,'origin':'human_source_supported','source_extractor':src.extractor_version,'source_bytes_hash':src.bytes_hash,'source_text_hash':src.text_hash,
        'extractor_confidence':{'status':'UNKNOWN'},'confidence_notice':'Reviewer assessments are declared opinions, not calibrated financial accuracy.','identifier_validation':'Source-declared identifiers; no external registry or checksum verification.'}
    context=m.FinancialFactContext(**capture,fact_id=fid,revision=prior.revision+1 if prior else 1,previous_hash=prior.content_hash if prior else None,fact_hash=row.content_hash,
        reference_kind=row.reference_kind,reference_id=row.reference_id,reference_snapshot=row.reference_snapshot,dimensions_json=canonical(p.dimensions.model_dump(mode='json')),provenance_json=canonical(provenance),content_hash='',
        rationale=p.rationale,created_by=actor.id,created_at=clock(),request_key=p.request_key,input_hash=fingerprint)
    context.content_hash=digest(canonical(material(context,refs)).encode());db.add(context);db.flush()
    for ref in refs:ref.context_id=context.id;db.add(ref)
    db.flush();rw.audit_work(db,actor,policy,'financial_context.propose',context,[row,*refs]);value=output(db,actor,context);db.commit();return value

def decide(db,actor,cid,p):
    internal(actor);context=db.get(m.FinancialFactContext,cid)
    if not context:raise HTTPException(404,'Financial context unavailable')
    w.legal(actor,context.matter_id);db.scalar(select(m.Matter).where(m.Matter.id==context.matter_id).with_for_update())
    if p.content_hash!=context.content_hash:raise HTTPException(409,'Exact financial context hash required')
    ops={entry.operation for entry in decisions(db,cid)}
    if 'revoke' in ops or p.operation in ops or (p.operation in {'confirm','reject'} and ops):raise HTTPException(409,'Financial context decision already retained')
    row=db.get(m.FinancialFact,context.fact_id)
    if p.operation=='revoke':
        if actor.id!=context.created_by and R.SME not in actor.roles:raise HTTPException(403,'Context author or scoped SME revocation required')
        capture={key:getattr(context,key) for key in ['matter_id','source_id','retained_classification','retained_scope']}
    else:
        lifecycle.mutable(db,context.matter_id);context,row,src,policy,units,dimensions=read(db,actor,cid)
        if R.SME not in actor.roles or actor.id in {context.created_by,row.created_by}:raise HTTPException(403,'Independent source-cleared SME distinct from context and fact authors required')
        if latest(db,row.id).id!=cid:raise HTTPException(409,'Only the latest exact context version can be decided')
        if not active_fact(db,row):raise HTTPException(409,'Independently verified active underlying fact required')
        if not p.content_reviewed:raise HTTPException(422,'Explicit review of every context dimension, UNKNOWN field and exact evidence is required')
        capture=rw.capture(src,db.get(m.DocumentPolicyVersion,src.policy_id))
    decision=m.FinancialContextDecision(**capture,context_id=cid,operation=p.operation,content_hash=context.content_hash,actor_id=actor.id,content_reviewed=p.content_reviewed,rationale=p.rationale,occurred_at=clock())
    db.add(decision);db.flush()
    # Even revocation of inaccessible/stale content records only a scoped receipt.
    parent=db.get(m.DocumentPolicyVersion,db.get(m.SourceVersion,context.source_id).policy_id)
    rw.audit_work(db,actor,parent,'financial_context.'+p.operation,decision,audit_records(db,context.id));db.commit()
    return {'id':cid,'content_hash':context.content_hash,'state':state(db,context),'audience':'internal_only'}

def comparison(db,actor,p):
    internal(actor);w.legal(actor,p.matter_id)
    values=[];blocking=[]
    for side,fid,expected in [('left',p.left_id,p.left_context_hash),('right',p.right_id,p.right_context_hash)]:
        row,src,policy,units=fact(db,actor,fid)
        if row.matter_id!=p.matter_id:raise HTTPException(403,'Comparison facts must be in the selected matter')
        if not active_fact(db,row):raise HTTPException(409,'Two verified active facts required')
        context=latest(db,fid)
        if context is None:
            if expected is not None:raise HTTPException(409,'Loaded context version unavailable')
            blocking.append({'field':side+'.context','status':'UNKNOWN','reason':'No independent context version exists'});values.append((row,None,None));continue
        if expected!=context.content_hash:raise HTTPException(409,'Load both exact current context versions before comparing')
        context,row,src,policy,units,dimensions=read(db,actor,context.id)
        if not confirmed(db,context,row):blocking.append({'field':side+'.confirmation','status':'UNKNOWN','reason':'Current independent confirmation required'})
        values.append((row,context,dimensions))
    left,right=values
    for field in ['entity','metric','period_start','period_end','currency','accounting_basis','consolidation_scope']:
        if getattr(left[0],field)!=getattr(right[0],field):blocking.append({'field':field,'status':'INCOMPATIBLE','reason':'Existing fact dimensions differ; no FX, period or accounting inference'})
    for field in FIELDS:
        pair=[getattr(item[2],field) if item[2] else None for item in values]
        if any(value is None or value.status=='UNKNOWN' for value in pair):blocking.append({'field':field,'status':'UNKNOWN','reason':'Explicit confirmed source evidence is missing'});continue
        if field=='instruments':
            if any(identifier.scheme=='OTHER' or identifier.scheme=='TICKER' and not identifier.venue for value in pair for identifier in value.identifiers):blocking.append({'field':field,'status':'UNKNOWN','reason':'Instrument scheme or ticker venue is not uniquely declared'});continue
            normalized=[sorted((identifier.scheme,identifier.value,identifier.venue or '') for identifier in value.identifiers) for value in pair]
        elif field=='sign':normalized=[value.convention for value in pair] # Physical plus/minus can legitimately differ.
        else:normalized=[value.model_dump(mode='json') for value in pair]
        if normalized[0]!=normalized[1]:blocking.append({'field':field,'status':'INCOMPATIBLE','reason':'Declared source dimensions differ; human reconciliation required'})
    result={'status':'INCOMPATIBLE' if any(item['status']=='INCOMPATIBLE' for item in blocking) else 'UNKNOWN' if blocking else 'COMPATIBLE','blocking_fields':blocking,
        'left_id':p.left_id,'right_id':p.right_id,'context_hashes':[item[1].content_hash if item[1] else None for item in values],'calculation':None,
        'notice':'Internal context-aware assessment only. Legacy financial comparison and all bank JSON remain unchanged; no automatic reconciliation or publication.'}
    if not blocking:result['calculation']={'operator':'left_minus_right_and_percentage_against_absolute_right','currency':left[0].currency,**arithmetic(left[0].amount_text,right[0].amount_text)}
    for row,context,dimensions in values:
        src=db.get(m.SourceVersion,row.source_id);policy=db.get(m.DocumentPolicyVersion,src.policy_id)
        rw.audit_work(db,actor,policy,'financial_context.compare',context or row,audit_records(db,context.id) if context else [row])
    return result

CANDIDATE_FIELDS=['matter_id','source_id','retained_classification','retained_scope','source_snapshot','extractor_version','anchor_key','candidate_key','raw_number','amount_text','entity','metric','period_start','period_end','currency','scale','accounting_basis','consolidation_scope','state','dimensions_json','missing_json','evidence_json','provenance_json','normalized_json']

def candidate_material(row):return {field:getattr(row,field) for field in CANDIDATE_FIELDS}

def candidate_read(db,actor,cid):
    internal(actor);row=db.get(m.FinancialExtractionCandidate,cid)
    if not row:raise HTTPException(404,'Financial extraction candidate unavailable')
    src,policy,units=finance.reference(db,actor,'source',row.source_id)
    rw.retained(db,actor,row)
    if row.matter_id!=src.matter_id or row.source_snapshot!=w.snapshot(db,policy) or digest(canonical(candidate_material(row)).encode())!=row.content_hash:raise HTTPException(403,'Financial candidate provenance changed; explicit new staging required')
    by={unit['number']:unit for unit in units}
    for ref in json.loads(row.evidence_json):
        unit=by.get(ref['unit'])
        if not unit or not 0<=ref['start']<ref['end']<=len(unit['text']) or unit['text'][ref['start']:ref['end']]!=ref['quote']:raise HTTPException(403,'Financial candidate evidence integrity denied')
    return row,src,policy

def candidate_output(db,actor,cid):
    row,src,policy=candidate_read(db,actor,cid)
    rw.audit_work(db,actor,policy,'financial_context.candidate_read',row)
    return {'id':row.id,'matter_id':row.matter_id,'source_id':row.source_id,'source_snapshot':row.source_snapshot,'anchor':row.anchor_key,'content_hash':row.content_hash,'state':row.state,
        'known_fields':{field:getattr(row,field) for field in ['raw_number','amount_text','entity','metric','period_start','period_end','currency','scale','accounting_basis','consolidation_scope']},
        'dimensions':json.loads(row.dimensions_json),'missing_fields':json.loads(row.missing_json),'evidence':[{**ref,'reader':{'id':row.source_id,'unit':ref['unit'],'start':ref['start'],'end':ref['end']}} for ref in json.loads(row.evidence_json)],
        'provenance':json.loads(row.provenance_json),'normalized':json.loads(row.normalized_json) if row.normalized_json else None,'created_at':row.created_at,'created_by':row.created_by,
        'approval':'UNAPPROVED','audience':'internal_only','notice':'Staging is not a financial fact, verification or release. No candidate is automatically promoted. Confidence remains UNKNOWN.'}

def candidate_list(db,actor,sid):
    internal(actor);finance.reference(db,actor,'source',sid)
    rows=list(db.scalars(select(m.FinancialExtractionCandidate).where(m.FinancialExtractionCandidate.source_id==sid).order_by(m.FinancialExtractionCandidate.created_at,m.FinancialExtractionCandidate.id).limit(101)))
    if len(rows)>100:raise HTTPException(413,'Local staging exceeds the 100-candidate read limit')
    return [candidate_output(db,actor,row.id) for row in rows]

def scan(db,actor,sid,p):
    from pathlib import Path
    from decimal import Decimal
    from kestrel.adapters import financial_candidates as adapter
    internal(actor);src,policy,units=finance.reference(db,actor,'source',sid,True)
    suffix=Path(src.file_name).suffix.lower()
    if p.extractor=='literal_rows_v1' and suffix not in {'.xlsx','.xlsm','.csv'} or p.extractor=='xbrl_v1' and suffix not in {'.xbrl','.xml','.ixbrl','.xhtml','.html','.htm'}:raise HTTPException(415,'The selected deterministic extractor does not match this retained source format')
    fingerprint=digest(canonical({'source_id':sid,'payload':p.model_dump(mode='json')}).encode())
    old=list(db.scalars(select(m.FinancialExtractionCandidate).where(m.FinancialExtractionCandidate.created_by==actor.id,m.FinancialExtractionCandidate.request_key==p.request_key)))
    if any(row.input_hash!=fingerprint for row in old):raise HTTPException(409,'Extraction request key changed')
    if old:return [candidate_output(db,actor,row.id) for row in old]
    values=adapter.extract(units,p.extractor,p.limit);snapshot=w.snapshot(db,policy);capture=rw.capture(src,db.get(m.DocumentPolicyVersion,src.policy_id));rows=[]
    from sqlalchemy import func
    existing=db.scalar(select(func.count()).select_from(m.FinancialExtractionCandidate).where(m.FinancialExtractionCandidate.source_id==sid))
    for value in values:
        key=digest(canonical({'source':sid,'snapshot':snapshot,'anchor':value['anchor_key'],'extractor':adapter.VERSION,'mode':p.extractor}).encode())
        retained=db.scalar(select(m.FinancialExtractionCandidate).where(m.FinancialExtractionCandidate.candidate_key==key))
        if retained:rows.append(retained);continue
        existing+=1
        if existing>100:raise HTTPException(413,'Local staging limit reached; no partial stage was committed')
        row=m.FinancialExtractionCandidate(**capture,source_snapshot=snapshot,extractor_version=adapter.VERSION,anchor_key=value['anchor_key'],candidate_key=key,
            **{field:value[field] for field in ['raw_number','amount_text','entity','metric','period_start','period_end','currency','scale','accounting_basis','consolidation_scope','state']},
            amount=Decimal(value['amount_text']) if value['amount_text'] is not None else None,dimensions_json=canonical(value['dimensions']),missing_json=canonical(value['missing']),evidence_json=canonical(value['evidence']),
            provenance_json=canonical({**value['provenance'],'source_bytes_hash':src.bytes_hash,'source_text_hash':src.text_hash,'source_extractor':src.extractor_version,'rationale':p.rationale}),normalized_json=canonical(value['normalized']) if value['normalized'] else None,
            content_hash='',created_by=actor.id,created_at=clock(),request_key=p.request_key,input_hash=fingerprint)
        row.content_hash=digest(canonical(candidate_material(row)).encode());db.add(row);db.flush();rw.audit_work(db,actor,policy,'financial_context.stage',row);rows.append(row)
    value=[candidate_output(db,actor,row.id) for row in rows];db.commit();return value
